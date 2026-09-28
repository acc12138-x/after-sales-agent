"""订单模型：客户购买记录 + 保修信息。"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import Column, DateTime, Integer, Numeric, String
from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    customer_id = Column(String(32), index=True)
    product_sku = Column(String(64))
    product_name = Column(String(128))
    category = Column(String(32), default="")
    quantity = Column(Integer, default=1)
    amount = Column(Numeric(10, 2), default=0)
    status = Column(String(32), default="paid")  # paid / shipped / delivered / refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    warranty_days = Column(Integer, default=365)

    @property
    def warranty_end(self):
        if not self.delivered_at:
            return None
        return self.delivered_at + timedelta(days=self.warranty_days or 365)

    @property
    def days_since_delivered(self):
        if not self.delivered_at:
            return None
        return (datetime.utcnow() - self.delivered_at).days

    @property
    def in_warranty(self):
        we = self.warranty_end
        return bool(we and datetime.utcnow() <= we)

    def to_dict(self):
        def _iso(dt): return dt.isoformat() if dt else None
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "product_sku": self.product_sku,
            "product_name": self.product_name,
            "category": self.category,
            "quantity": self.quantity,
            "amount": float(self.amount or 0),
            "status": self.status,
            "created_at": _iso(self.created_at),
            "delivered_at": _iso(self.delivered_at),
            "warranty_days": self.warranty_days,
            "warranty_end": _iso(self.warranty_end),
            "in_warranty": self.in_warranty,
            "days_since_delivered": self.days_since_delivered,
        }
