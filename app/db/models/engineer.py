"""Engineer 模型：售后工程师。"""
from __future__ import annotations
import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.base import Base


class Engineer(Base):
    __tablename__ = "engineers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    skills = Column(Text, default="[]")            # JSON list: ["E102","E200"]
    region = Column(String(64), default="")
    phone = Column(String(32), default="")
    feishu_open_id = Column(String(128), default="")   # 飞书通知用
    status = Column(String(16), default="online")      # online / offline / busy
    current_load = Column(Integer, default=0)          # 当前工单数
    max_load = Column(Integer, default=10)             # 最大承接数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def skill_list(self) -> list:
        try:
            return json.loads(self.skills or "[]")
        except Exception:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "skills": self.skill_list,
            "region": self.region,
            "phone": self.phone,
            "feishu_open_id": self.feishu_open_id,
            "status": self.status,
            "current_load": self.current_load,
            "max_load": self.max_load,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
