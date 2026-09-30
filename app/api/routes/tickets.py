from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.schemas.models import (
    TicketCreateRequest, TicketResponse, TicketUpdateRequest,
)
from app.audit.logger import log as audit_log
from app.db.models.user import User
from app.db.models.ticket import Ticket
from app.db.session import session_scope
from app.notify.notifier import send as notify
from app.services.sla_service import compute_deadline, get_ticket_sla_info


router = APIRouter(prefix="/tickets", tags=["tickets"])


class RejectRequest(BaseModel):
    reason: str = ""


class ResolveRequest(BaseModel):
    note: str = ""


# ---------- 内部工具 ----------
ACTIVE_STATUSES = {"pending", "assigned", "accepted", "in_progress"}


def _broadcast_group(event: str, title: str, content: str) -> None:
    """私聊之外，把事件同步广播到配置好的群（webhook 在 .env 里配）。

    失败不影响主流程。
    """
    try:
        from app.services.feishu_router import broadcast
        broadcast(event=event, title=title, content=content)
    except Exception as e:
        print(f"[NOTIFY] group broadcast failed: {e}")


def _sync_engineer_load(s, ticket, old_status: str, new_status: str):
    """工单状态变更时同步工程师 current_load。

    规则：
    - 活跃(pending/assigned/accepted/in_progress) → 非活跃(resolved/closed/rejected/cancelled)：-1
    - 非活跃 → 活跃：+1
    - 其它情况：不变
    """
    if not ticket.assigned_engineer_id:
        return
    was_active = old_status in ACTIVE_STATUSES
    is_active = new_status in ACTIVE_STATUSES
    if was_active == is_active:
        return
    eng = s.get(User, ticket.assigned_engineer_id)
    if eng is None:
        return
    if is_active:
        eng.current_load = (eng.current_load or 0) + 1
    else:
        eng.current_load = max(0, (eng.current_load or 0) - 1)


def _pick_engineer(s, error_code: Optional[str], exclude_names: Optional[list] = None):
    exclude_names = exclude_names or []
    rows = s.execute(select(User).where(User.role == "engineer", User.status == "online")).scalars().all()
    candidates = [e for e in rows
                  if e.current_load < e.max_load and e.name not in exclude_names]
    if not candidates:
        return None
    if error_code:
        skilled = [e for e in candidates if error_code in e.skill_list]
        pool = skilled if skilled else candidates
    else:
        pool = candidates
    pool.sort(key=lambda x: (x.current_load, x.id))
    return pool[0]


def _compute_missing(device_model: Optional[str], error_code: Optional[str]) -> str:
    """返回缺失字段的逗号分隔字符串。空字符串 = 完整。"""
    missing = []
    if not (device_model or "").strip():
        missing.append("device_model")
    if not (error_code or "").strip():
        missing.append("error_code")
    return ",".join(missing)


# ---------- 建单 ----------
def do_create_ticket(
    device_model: Optional[str] = None,
    error_code: Optional[str] = None,
    description: str = "",
    contact: str = "",
    address: str = "",
    urgent: bool = False,
    code_verified: bool = True,
) -> dict:
    """创建工单。

    规则：
    - device_model / error_code 至少提供一个，否则 400
    - 只提供其中一个 -> 允许建单，标记 missing_fields
    - 都提供 -> 完整工单
    """
    device_model = (device_model or "").strip() or None
    error_code = (error_code or "").strip() or None

    if not device_model and not error_code:
        raise HTTPException(
            status_code=400,
            detail="设备型号（device_model）和故障码（error_code）至少提供一个",
        )

    tid = f"T{uuid4().hex[:8].upper()}"
    missing = _compute_missing(device_model, error_code)

    with session_scope() as s:
        engineer = _pick_engineer(s, error_code)
        if engineer is None:
            raise HTTPException(status_code=503, detail="当前无可用工程师")

        created = datetime.now()
        # 从意图推断 ticket_type（如有）
        ttype = "repair"
        if description:
            dl = description.lower()
            if "退款" in dl: ttype = "refund"
            elif "退货" in dl: ttype = "return"
            elif "换货" in dl: ttype = "exchange"
            elif "投诉" in dl: ttype = "complaint"

        t = Ticket(
            ticket_id=tid,
            status="assigned",
            assigned_to=engineer.name,
            assigned_engineer_id=engineer.id,
            device_model=device_model,
            error_code=error_code,
            description=description,
            contact=contact,
            address=address,
            missing_fields=missing,
            ticket_type=ttype,
            created_at=created,
            assigned_at=created,
            assign_count=1,
            sla_deadline=compute_deadline(ttype, urgent=urgent, created_at=created),
            sla_status="normal",
            code_verified=code_verified,
        )
        s.add(t)
        engineer.current_load = (engineer.current_load or 0) + 1
        s.flush()

        result = t.to_dict()
        engineer_name = engineer.name
        engineer_id = engineer.id

    # 会话外只使用普通变量
    notify(
        target=engineer_name,
        event="ticket_assigned",
        title=f"新工单 {tid}",
        content=f"设备 {device_model or '待补充'} 故障码 {error_code or '待补充'}，请及时处理。",
    )
    _broadcast_group(
        event="ticket_assigned",
        title=f"新工单 {tid} → {engineer_name}",
        content=(f"设备 {device_model or '待补充'}｜"
                 f"故障码 {error_code or '待补充'}｜已派给 {engineer_name}。"),
    )
    audit_log(
        action="ticket.created",
        actor="system",
        target_type="ticket",
        target_id=tid,
        detail={
            "engineer": engineer_name,
            "error_code": error_code,
            "missing": missing,
        },
    )
    result["engineer_id"] = engineer_id
    return result


# ---------- 补全 ----------
def do_update_ticket(ticket_id: str, req: TicketUpdateRequest) -> dict:
    """补全或修改工单字段。只处理非 None 的字段。"""
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="工单不存在")
        if t.status in ("closed", "cancelled"):
            raise HTTPException(status_code=400, detail=f"工单已 {t.status}，无法修改")

        changed = {}
        for field in ("device_model", "error_code", "description", "contact", "address"):
            val = getattr(req, field, None)
            if val is None:
                continue
            val = str(val).strip()
            old = getattr(t, field)
            if val and val != (old or ""):
                setattr(t, field, val)
                changed[field] = {"old": old, "new": val}

        if not changed:
            return t.to_dict()

        # 重新计算缺失字段
        t.missing_fields = _compute_missing(t.device_model, t.error_code)
        t.updated_at = datetime.now()
        s.flush()
        result = t.to_dict()

    audit_log(
        action="ticket.updated",
        actor="api",
        target_type="ticket",
        target_id=ticket_id,
        detail={"changes": changed},
    )
    return result


# ---------- API ----------
@router.post("", response_model=TicketResponse)
async def create_ticket(req: TicketCreateRequest) -> TicketResponse:
    t = do_create_ticket(
        device_model=req.device_model,
        error_code=req.error_code,
        description=req.description,
        contact=req.contact,
        address=req.address,
    )
    return TicketResponse(
        ticket_id=t["ticket_id"],
        status=t["status"],
        assigned_to=t["assigned_to"],
        created_at=t["created_at"],
    )


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, req: TicketUpdateRequest):
    return do_update_ticket(ticket_id, req)


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        return t.to_dict()


@router.get("")
async def list_all_tickets(
    status: Optional[str] = None,
    incomplete_only: bool = False,
    keyword: Optional[str] = None,
):
    from sqlalchemy import or_
    with session_scope() as s:
        q = select(Ticket).order_by(Ticket.created_at.desc())
        if status:
            q = q.where(Ticket.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.where(or_(
                Ticket.ticket_id.like(kw),
                Ticket.device_model.like(kw),
                Ticket.error_code.like(kw),
                Ticket.assigned_to.like(kw),
                Ticket.description.like(kw),
                Ticket.contact.like(kw),
            ))
        rows = s.execute(q).scalars().all()
        items = []
        for t in rows:
            d = t.to_dict()
            d.update(get_ticket_sla_info(t))
            items.append(d)
        if incomplete_only:
            items = [x for x in items if not x["is_complete"]]
    return {"total": len(items), "items": items}


# ---------- 状态机 ----------
def _transition(ticket_id: str, new_status: str, extra: dict = None) -> dict:
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        if not t.can_transition_to(new_status):
            raise HTTPException(
                status_code=400,
                detail=f"不允许从 {t.status} 流转到 {new_status}",
            )

        # 建单必填项完整才能开始处理（生产约束）
        if new_status in ("accepted", "in_progress") and not t.is_complete:
            raise HTTPException(
                status_code=400,
                detail=f"工单信息不完整（缺: {','.join(t.missing_list)}），请先补全",
            )

        old_status = t.status
        t.status = new_status
        t.updated_at = datetime.now()
        if extra:
            for k, v in extra.items():
                setattr(t, k, v)

        if new_status == "accepted":
            t.accepted_at = datetime.now()
        elif new_status == "resolved":
            t.resolved_at = datetime.now()
        elif new_status == "closed":
            t.closed_at = datetime.now()

        # 统一同步负载（不会重复减，跨活跃边界才动）
        _sync_engineer_load(s, t, old_status, new_status)

        result = t.to_dict()
        result["_old_status"] = old_status

    audit_log(
        action=f"ticket.{new_status}",
        actor="api",
        target_type="ticket",
        target_id=ticket_id,
        detail={"from": result["_old_status"], "to": new_status},
    )
    return result


@router.post("/{ticket_id}/accept")
async def accept_ticket(ticket_id: str):
    r = _transition(ticket_id, "accepted")
    notify(target=r["assigned_to"], event="ticket_accepted",
           title=f"工单 {ticket_id} 已接单")
    _broadcast_group(event="ticket_accepted",
                     title=f"工单 {ticket_id} 已接单",
                     content=f"工程师：{r.get('assigned_to') or '-'}")
    return r


@router.post("/{ticket_id}/reject")
async def reject_ticket(ticket_id: str, req: RejectRequest):
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        if t.status not in ("assigned", "accepted", "in_progress"):
            raise HTTPException(status_code=400, detail=f"当前状态 {t.status} 不能拒单")

        old_engineer = t.assigned_to
        if t.assigned_engineer_id:
            old_eng = s.get(User, t.assigned_engineer_id)
            if old_eng and old_eng.current_load > 0:
                old_eng.current_load -= 1

        new_eng = _pick_engineer(s, t.error_code, exclude_names=[old_engineer])
        if new_eng is None:
            t.status = "rejected"
            t.reject_reason = req.reason
            result = t.to_dict()
        else:
            t.status = "assigned"
            t.assigned_to = new_eng.name
            t.assigned_engineer_id = new_eng.id
            t.reject_reason = req.reason
            t.assign_count = (t.assign_count or 0) + 1
            t.assigned_at = datetime.now()
            new_eng.current_load += 1
            result = t.to_dict()
            result["new_engineer"] = new_eng.name

    notify(target=old_engineer, event="ticket_rejected",
           title=f"工单 {ticket_id} 已拒单", content=req.reason or "无原因")
    re_msg = (f"，已重派给 {result['new_engineer']}" if result.get("new_engineer")
              else "，暂无可用工程师重派")
    _broadcast_group(
        event="ticket_rejected",
        title=f"工单 {ticket_id} 已拒单",
        content=f"{old_engineer} 拒单{re_msg}。原因：{req.reason or '无'}",
    )
    if result.get("new_engineer"):
        notify(target=result["new_engineer"], event="ticket_assigned",
               title=f"新工单 {ticket_id}", content="请及时处理")
        _broadcast_group(
            event="ticket_assigned",
            title=f"工单 {ticket_id} 已重派 → {result['new_engineer']}",
            content=f"原工程师 {old_engineer} 拒单，已改派给 {result['new_engineer']}。",
        )
    audit_log(action="ticket.rejected", actor="api", target_type="ticket",
              target_id=ticket_id,
              detail={"reason": req.reason, "old": old_engineer})
    return result


@router.post("/{ticket_id}/start")
async def start_ticket(ticket_id: str):
    return _transition(ticket_id, "in_progress")


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, req: ResolveRequest):
    return _transition(ticket_id, "resolved", extra={"resolved_note": req.note})


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: str):
    return _transition(ticket_id, "closed")


# ---------- 审计 / 通知 ----------
@router.get("/{ticket_id}/audit")
async def get_ticket_audit(ticket_id: str, limit: int = 50):
    from app.db.models.audit_log import AuditLog
    with session_scope() as s:
        rows = s.execute(
            select(AuditLog)
            .where(AuditLog.target_id == ticket_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return {"items": [r.to_dict() for r in rows]}


@router.get("/{ticket_id}/notifications")
async def get_ticket_notifications(ticket_id: str, limit: int = 50):
    from app.db.models.notification import Notification
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        rows = s.execute(
            select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        ).scalars().all()
        items = [r.to_dict() for r in rows
                 if ticket_id in (r.title or "") or ticket_id in (r.content or "")]
        return {"items": items}
