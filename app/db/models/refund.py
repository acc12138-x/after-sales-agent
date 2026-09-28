"""退款/赔付申请模型。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Numeric, String, Text
from app.db.base import Base


# 状态机
REFUND_FLOW = {
    "pending":           ["ai_review", "cancelled"],
    "ai_review":         ["pending_approval", "approved", "rejected"],
    "pending_approval":  ["approved", "rejected"],
    "approved":          ["executed"],
    "executed":          [],
    "rejected":          [],
    "cancelled":         [],
}


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    refund_id = Column(String(32), primary_key=True)
    ticket_id = Column(String(32), index=True)
    customer_id = Column(String(32), index=True)
    order_id = Column(String(64))
    refund_type = Column(String(32), default="refund_only")
    # refund_only / return_refund / compensation / shipping_fee
    amount = Column(Numeric(10, 2), default=0)
    reason = Column(Text, default="")
    status = Column(String(32), default="pending", index=True)
    ai_suggestion = Column(String(32), default="")  # approve / reject / need_human
    ai_confidence = Column(Float, default=0.0)
    ai_reason = Column(Text, default="")
    risk_flag = Column(String(16), default="")
    approver = Column(String(64), nullable=True)
    approval_note = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in REFUND_FLOW.get(self.status, [])

    def to_dict(self):
        def _iso(dt): return dt.isoformat() if dt else None
        return {
            "refund_id": self.refund_id,
            "ticket_id": self.ticket_id,
            "customer_id": self.customer_id,
            "order_id": self.order_id,
            "refund_type": self.refund_type,
            "amount": float(self.amount or 0),
            "reason": self.reason,
            "status": self.status,
            "ai_suggestion": self.ai_suggestion,
            "ai_confidence": self.ai_confidence,
            "ai_reason": self.ai_reason,
            "risk_flag": self.risk_flag,
            "approver": self.approver,
            "approval_note": self.approval_note,
            "approved_at": _iso(self.approved_at),
            "executed_at": _iso(self.executed_at),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }
