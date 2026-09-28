"""Ticket 模型（状态机 + 字段完整度）。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.db.base import Base


STATUS_FLOW = {
    "pending":     ["assigned", "cancelled"],
    "assigned":    ["accepted", "rejected", "cancelled"],
    "accepted":    ["in_progress", "rejected"],
    "in_progress": ["resolved", "rejected"],
    "resolved":    ["closed", "in_progress"],
    "closed":      [],
    "rejected":    ["assigned"],
    "cancelled":   [],
}


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String(32), primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    assigned_to = Column(String(64))
    assigned_engineer_id = Column(Integer)

    # 核心字段（允许 NULL —— 支持"待补充"工单）
    device_model = Column(String(128), nullable=True)
    error_code = Column(String(64), nullable=True)
    description = Column(Text)
    contact = Column(String(256))
    address = Column(String(512))

    # 完整度标记：逗号分隔的缺失字段名，空字符串 = 完整
    missing_fields = Column(String(256), default="")

    # 状态机相关
    reject_reason = Column(String(256))
    resolved_note = Column(Text)
    assign_count = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime)
    accepted_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_complete(self) -> bool:
        return not (self.missing_fields or "").strip()

    @property
    def missing_list(self) -> list:
        mf = (self.missing_fields or "").strip()
        return [x for x in mf.split(",") if x]

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in STATUS_FLOW.get(self.status, [])

    def to_dict(self) -> dict:
        def _iso(dt):
            return dt.isoformat() if dt else None
        return {
            "ticket_id": self.ticket_id,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assigned_engineer_id": self.assigned_engineer_id,
            "device_model": self.device_model,
            "error_code": self.error_code,
            "description": self.description,
            "contact": self.contact,
            "address": self.address,
            "is_complete": self.is_complete,
            "missing_fields": self.missing_list,
            "reject_reason": self.reject_reason,
            "resolved_note": self.resolved_note,
            "assign_count": self.assign_count,
            "created_at": _iso(self.created_at),
            "assigned_at": _iso(self.assigned_at),
            "accepted_at": _iso(self.accepted_at),
            "resolved_at": _iso(self.resolved_at),
            "closed_at": _iso(self.closed_at),
            "updated_at": _iso(self.updated_at),
        }
