"""待绑定飞书账号：记录发过消息、但尚未绑定到系统用户的 open_id。

用途：用户在飞书给机器人发消息时，后端已能拿到其 open_id，
但无法知道他是系统里的哪个人。这里把"陌生 open_id"攒起来，
管理员在「人员管理」页面一键绑定即可，免去手工复制粘贴。
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from app.db.base import Base


class PendingBinding(Base):
    __tablename__ = "pending_bindings"

    open_id = Column(String(128), primary_key=True)
    chat_id = Column(String(128), default="")
    last_text = Column(String(256), default="")
    message_count = Column(Integer, default=0)
    first_seen = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict:
        def _iso(dt):
            return dt.isoformat() if dt else None
        return {
            "open_id": self.open_id,
            "chat_id": self.chat_id or "",
            "last_text": self.last_text or "",
            "message_count": self.message_count or 0,
            "first_seen": _iso(self.first_seen),
            "last_seen": _iso(self.last_seen),
        }
