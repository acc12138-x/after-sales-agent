"""审计日志模型。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(64), default="system")       # 谁操作
    action = Column(String(64), nullable=False)         # 什么动作
    target_type = Column(String(32), default="")        # 目标类型
    target_id = Column(String(64), default="")          # 目标 ID
    detail = Column(Text, default="")                   # JSON 详情
    result = Column(String(16), default="ok")           # ok / fail
    created_at = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "detail": self.detail,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
