"""主管审批工作台 API。"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.routes.auth import get_current_user
from app.audit.logger import log as audit_log
from app.db.models.refund import RefundRequest
from app.db.models.ticket import Ticket
from app.db.session import session_scope

router = APIRouter(prefix="/approvals", tags=["approvals"])


# ============================================================
# Schemas
# ============================================================
class BatchApproveRequest(BaseModel):
    refund_ids: List[str] = []
    note: str = ""


class RejectRequest(BaseModel):
    refund_id: str
    note: str = ""


class BatchRefundApprove(BaseModel):
    refund_ids: List[str]
    decision: str  # approve / reject
    note: str = ""


# ============================================================
# 聚合待审批列表
# ============================================================
@router.get("/pending")
async def list_pending(user: dict = Depends(get_current_user)):
    """返回所有需要主管处理的项。"""
    if not user.get("effective_permissions") or (
        "refund.approve" not in user["effective_permissions"]
        and "*" not in user["effective_permissions"]
    ):
        raise HTTPException(status_code=403, detail="需要主管权限")

    items = []

    with session_scope() as s:
        # 1. 待审批退款
        refunds = s.execute(
            select(RefundRequest).where(
                RefundRequest.status.in_(["pending", "ai_review", "pending_approval"])
            ).order_by(RefundRequest.created_at.desc())
        ).scalars().all()

        for r in refunds:
            items.append({
                "type": "refund",
                "id": r.refund_id,
                "amount": float(r.amount or 0),
                "customer_id": r.customer_id,
                "order_id": r.order_id,
                "reason": r.reason,
                "status": r.status,
                "ai_suggestion": r.ai_suggestion,
                "ai_confidence": r.ai_confidence,
                "ai_reason": r.ai_reason,
                "risk_flag": r.risk_flag,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "urgency": "high" if r.risk_flag or float(r.amount or 0) > 2000 else "normal",
            })

        # 2. SLA 超时工单
        overdue = s.execute(
            select(Ticket).where(
                Ticket.sla_status == "overdue",
                Ticket.status.notin_(["resolved", "closed", "cancelled"]),
            )
        ).scalars().all()

        for t in overdue:
            items.append({
                "type": "overdue_ticket",
                "id": t.ticket_id,
                "ticket_id": t.ticket_id,
                "assigned_to": t.assigned_to,
                "device_model": t.device_model,
                "error_code": t.error_code,
                "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
                "sla_status": t.sla_status,
                "reason": f"SLA 超时（截止 {t.sla_deadline}）",
                "urgency": "high",
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

    # 按紧急度排序
    items.sort(key=lambda x: (0 if x.get("urgency") == "high" else 1, x.get("created_at") or ""))

    return {
        "total": len(items),
        "refunds": [x for x in items if x["type"] == "refund"],
        "overdue_tickets": [x for x in items if x["type"] == "overdue_ticket"],
    }


# ============================================================
# 批量审批退款
# ============================================================
@router.post("/refunds/batch")
async def batch_approve_refund(
    req: BatchRefundApprove,
    user: dict = Depends(get_current_user),
):
    """批量审批退款。decision=approve/reject。"""
    if "refund.approve" not in (user.get("effective_permissions") or []) and "*" not in (user.get("effective_permissions") or []):
        raise HTTPException(status_code=403, detail="需要退款审批权限")

    if req.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision 必须是 approve/reject")

    if not req.refund_ids:
        raise HTTPException(status_code=400, detail="refund_ids 不能为空")

    updated = []
    failed = []

    with session_scope() as s:
        for rid in req.refund_ids:
            r = s.get(RefundRequest, rid)
            if r is None:
                failed.append({"id": rid, "reason": "不存在"})
                continue
            if r.status not in ("pending", "ai_review", "pending_approval"):
                failed.append({"id": rid, "reason": f"状态 {r.status} 不可审批"})
                continue

            r.status = "approved" if req.decision == "approve" else "rejected"
            r.approver = user.get("name") or "supervisor"
            r.approval_note = req.note or f"主管批量{'通过' if req.decision == 'approve' else '驳回'}"
            r.approved_at = datetime.utcnow()
            updated.append(rid)

    # 审计
    audit_log(
        action=f"refund.batch_{req.decision}",
        actor=user.get("name") or "supervisor",
        target_type="refund",
        target_id=",".join(updated[:5]),
        detail={"count": len(updated), "note": req.note},
    )

    return {
        "updated": updated,
        "failed": failed,
        "count": len(updated),
    }


# ============================================================
# 超时工单改派
# ============================================================
@router.post("/tickets/{ticket_id}/reassign")
async def reassign_overdue_ticket(
    ticket_id: str,
    user: dict = Depends(get_current_user),
):
    """改派超时工单给下一个可用工程师。"""
    if "ticket.reassign" not in (user.get("effective_permissions") or []) and "*" not in (user.get("effective_permissions") or []):
        raise HTTPException(status_code=403, detail="需要改派权限")

    from app.api.routes.tickets import _pick_engineer
    from app.db.models.engineer import Engineer

    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="工单不存在")

        old = t.assigned_to
        if t.assigned_engineer_id:
            oe = s.get(Engineer, t.assigned_engineer_id)
            if oe and oe.current_load > 0:
                oe.current_load -= 1

        new_eng = _pick_engineer(s, t.error_code, exclude_names=[old])
        if new_eng is None:
            raise HTTPException(status_code=503, detail="无可用工程师")

        t.assigned_to = new_eng.name
        t.assigned_engineer_id = new_eng.id
        t.assign_count = (t.assign_count or 0) + 1
        t.assigned_at = datetime.utcnow()
        new_eng.current_load += 1

        result = {
            "ticket_id": t.ticket_id,
            "old_engineer": old,
            "new_engineer": new_eng.name,
            "assign_count": t.assign_count,
        }

    audit_log(
        action="ticket.reassigned_by_supervisor",
        actor=user.get("name") or "supervisor",
        target_type="ticket",
        target_id=ticket_id,
        detail=result,
    )

    return result


# ============================================================
# 统计
# ============================================================
@router.get("/stats")
async def approval_stats(user: dict = Depends(get_current_user)):
    with session_scope() as s:
        from sqlalchemy import func
        refund_pending = s.execute(
            select(func.count(RefundRequest.refund_id))
            .where(RefundRequest.status == "pending_approval")
        ).scalar() or 0
        refund_approved = s.execute(
            select(func.count(RefundRequest.refund_id))
            .where(RefundRequest.status == "approved")
        ).scalar() or 0
        overdue = s.execute(
            select(func.count(Ticket.ticket_id))
            .where(Ticket.sla_status == "overdue", Ticket.status.notin_(["resolved", "closed", "cancelled"]))
        ).scalar() or 0
        return {
            "refund_pending": refund_pending,
            "refund_approved": refund_approved,
            "overdue_tickets": overdue,
            "total_pending": refund_pending + overdue,
        }
