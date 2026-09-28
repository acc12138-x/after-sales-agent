"""通知记录（模拟）模型。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(32), default="feishu")     # feishu / sms / email
    target = Column(String(128), nullable=False)       # 工程师姓名 / open_id
    event = Column(String(64), nullable=False)         # ticket_assigned / ticket_rejected ...
    title = Column(String(256), default="")
    content = Column(Text, default="")
    status = Column(String(16), default="sent")        # sent / failed / pending
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "channel": self.channel,
            "target": self.target,
            "event": self.event,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
