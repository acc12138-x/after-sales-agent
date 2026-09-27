"""Ticket 模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String(32), primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    assigned_to = Column(String(64))
    device_model = Column(String(128))
    error_code = Column(String(64))
    description = Column(Text)
    contact = Column(String(256))
    address = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "device_model": self.device_model,
            "error_code": self.error_code,
            "description": self.description,
            "contact": self.contact,
            "address": self.address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
