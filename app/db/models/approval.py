"""审批流配置模型。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, String, Text
from app.db.base import Base


class ApprovalFlow(Base):
    __tablename__ = "approval_flows"

    flow_id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    trigger_type = Column(String(32))  # refund / high_value_ticket / complaint
    conditions = Column(Text, default="{}")  # JSON 条件
    steps = Column(Text, default="[]")  # JSON 步骤列表
    enabled = Column(Boolean, default=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        import json
        return {
            "flow_id": self.flow_id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "conditions": json.loads(self.conditions or "{}"),
            "steps": json.loads(self.steps or "[]"),
            "enabled": self.enabled,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
