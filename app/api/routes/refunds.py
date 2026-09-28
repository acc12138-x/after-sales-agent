"""退款 / 赔付 API。"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas.models import (
    RefundApprovalRequest, RefundCreateRequest, RefundResponse,
)
from app.audit.logger import log as audit_log
from app.db.models.customer import Customer
from app.db.models.refund import RefundRequest
from app.db.session import session_scope
from app.notify.notifier import send as notify
from app.services.risk_service import auto_decision, check_risk

router = APIRouter(prefix="/refunds", tags=["refunds"])


def _to_resp(r: RefundRequest) -> RefundResponse:
    return RefundResponse(**r.to_dict())


@router.get("")
async def list_refunds(status: Optional[str] = None):
    with session_scope() as s:
        q = select(RefundRequest).order_by(RefundRequest.created_at.desc())
        if status:
            q = q.where(RefundRequest.status == status)
        rows = s.execute(q).scalars().all()
        return {"total": len(rows), "items": [r.to_dict() for r in rows]}


@router.post("", response_model=RefundResponse)
async def create_refund(req: RefundCreateRequest):
    """创建退款单：自动 AI 初审 + 风控。"""
    rid = f"RF{uuid4().hex[:8].upper()}"

    with session_scope() as s:
        c = s.get(Customer, req.customer_id)
        if c is None:
            raise HTTPException(status_code=404, detail="客户不存在")

        # 风控 + AI 初审
        risk = check_risk(req.customer_id)
        decision = auto_decision(req.customer_id, req.amount, req.refund_type)

        # 决定初始状态
        if decision["suggestion"] == "approve" and decision["confidence"] >= 0.85:
            status = "approved"  # 直接通过（但未执行）
        else:
            status = "pending_approval"

        r = RefundRequest(
            refund_id=rid,
            ticket_id=req.ticket_id,
            customer_id=req.customer_id,
            order_id=req.order_id,
            refund_type=req.refund_type,
            amount=req.amount,
            reason=req.reason,
            status=status,
            ai_suggestion=decision["suggestion"],
            ai_confidence=decision["confidence"],
            ai_reason=decision["reason"],
            risk_flag=risk["level"] if risk["level"] != "normal" else "",
            created_at=datetime.utcnow(),
        )
        s.add(r)
        s.flush()
        result = r.to_dict()

        # 客户退款次数 +1
        c.total_refunds = (c.total_refunds or 0) + 1

    # 通知 + 审计
    audit_log(
        action="refund.created",
        actor="system",
        target_type="refund",
        target_id=rid,
        detail={
            "amount": req.amount,
            "ai_suggestion": decision["suggestion"],
            "risk": risk["level"],
        },
    )
    return RefundResponse(**result)


@router.get("/{refund_id}")
async def get_refund(refund_id: str):
    with session_scope() as s:
        r = s.get(RefundRequest, refund_id)
        if r is None:
            raise HTTPException(status_code=404, detail="退款单不存在")
        return r.to_dict()


@router.post("/{refund_id}/approve")
async def approve_refund(refund_id: str, req: RefundApprovalRequest):
    """人工审批：同意 / 驳回。"""
    with session_scope() as s:
        r = s.get(RefundRequest, refund_id)
        if r is None:
            raise HTTPException(status_code=404, detail="退款单不存在")
        if r.status not in ("pending", "ai_review", "pending_approval"):
            raise HTTPException(status_code=400, detail=f"当前状态 {r.status} 不可审批")

        if req.decision == "approve":
            r.status = "approved"
        elif req.decision == "reject":
            r.status = "rejected"
        else:
            raise HTTPException(status_code=400, detail="decision 必须是 approve/reject")

        r.approver = "admin"
        r.approval_note = req.note
        r.approved_at = datetime.utcnow()
        s.flush()
        result = r.to_dict()

    audit_log(
        action=f"refund.{req.decision}d",
        actor="admin",
        target_type="refund",
        target_id=refund_id,
        detail={"note": req.note, "amount": result["amount"]},
    )
    notify(
        target=result["customer_id"],
        event=f"refund_{req.decision}d",
        title=f"退款单 {refund_id} 已{('通过' if req.decision == 'approve' else '驳回')}",
        content=req.note,
    )
    return result


@router.post("/{refund_id}/execute")
async def execute_refund(refund_id: str):
    """执行退款（模拟打款）。"""
    with session_scope() as s:
        r = s.get(RefundRequest, refund_id)
        if r is None:
            raise HTTPException(status_code=404, detail="退款单不存在")
        if r.status != "approved":
            raise HTTPException(status_code=400, detail=f"当前状态 {r.status} 不可执行")
        r.status = "executed"
        r.executed_at = datetime.utcnow()
        s.flush()
        result = r.to_dict()

    audit_log(
        action="refund.executed",
        actor="system",
        target_type="refund",
        target_id=refund_id,
        detail={"amount": result["amount"]},
    )
    return result


@router.get("/stats/summary")
async def refund_stats():
    from sqlalchemy import func
    with session_scope() as s:
        rows = s.execute(
            select(RefundRequest.status, func.count(RefundRequest.refund_id))
            .group_by(RefundRequest.status)
        ).all()
        dist = {r[0]: r[1] for r in rows}
        total_amount = s.execute(select(func.sum(RefundRequest.amount))).scalar() or 0
        return {"distribution": dist, "total_amount": float(total_amount)}

# ============================================================
# 同步核心函数（供 LangGraph 节点调用）
# ============================================================
def do_create_refund(
    customer_id: str,
    order_id: str,
    amount: float,
    refund_type: str = "refund_only",
    reason: str = "",
    ticket_id: str = "",
) -> dict:
    """同步创建退款单 + 风控 + AI 初审。返回 dict。"""
    rid = f"RF{uuid4().hex[:8].upper()}"

    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            raise ValueError(f"客户 {customer_id} 不存在")

        # 风控 + AI 初审
        risk = check_risk(customer_id)
        decision = auto_decision(customer_id, amount, refund_type)

        if decision["suggestion"] == "approve" and decision["confidence"] >= 0.85:
            status = "approved"
        else:
            status = "pending_approval"

        r = RefundRequest(
            refund_id=rid,
            ticket_id=ticket_id,
            customer_id=customer_id,
            order_id=order_id,
            refund_type=refund_type,
            amount=amount,
            reason=reason,
            status=status,
            ai_suggestion=decision["suggestion"],
            ai_confidence=decision["confidence"],
            ai_reason=decision["reason"],
            risk_flag=risk["level"] if risk["level"] != "normal" else "",
            created_at=datetime.utcnow(),
        )
        s.add(r)
        s.flush()
        result = r.to_dict()

        c.total_refunds = (c.total_refunds or 0) + 1

    # 审计
    audit_log(
        action="refund.created",
        actor="system",
        target_type="refund",
        target_id=rid,
        detail={"amount": amount, "ai_suggestion": decision["suggestion"], "risk": risk["level"]},
    )
    return result
