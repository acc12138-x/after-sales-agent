"""客户 + 订单 API。"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas.models import CustomerCreate, CustomerResponse
from app.db.models.customer import Customer
from app.db.models.order import Order
from app.db.models.ticket import Ticket
from app.db.models.refund import RefundRequest
from app.db.session import session_scope

router = APIRouter(prefix="/customers", tags=["customers"])


def _to_resp(c: Customer) -> CustomerResponse:
    return CustomerResponse(**c.to_dict())


@router.get("", response_model=list[CustomerResponse])
async def list_customers(vip_level: Optional[str] = None, risk_level: Optional[str] = None):
    with session_scope() as s:
        q = select(Customer).order_by(Customer.customer_id)
        if vip_level:
            q = q.where(Customer.vip_level == vip_level)
        if risk_level:
            q = q.where(Customer.risk_level == risk_level)
        rows = s.execute(q).scalars().all()
        return [_to_resp(c) for c in rows]


@router.post("", response_model=CustomerResponse)
async def create_customer(req: CustomerCreate):
    with session_scope() as s:
        exists = s.execute(select(Customer).where(Customer.phone == req.phone)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail="手机号已存在")
        cid = f"C{uuid4().hex[:6].upper()}"
        c = Customer(
            customer_id=cid,
            name=req.name,
            phone=req.phone,
            email=req.email,
            address=req.address,
            vip_level=req.vip_level,
        )
        s.add(c)
        s.flush()
        return _to_resp(c)


@router.get("/{customer_id}")
async def get_customer(customer_id: str):
    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        return c.to_dict()


@router.get("/{customer_id}/orders")
async def get_customer_orders(customer_id: str):
    with session_scope() as s:
        rows = s.execute(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [o.to_dict() for o in rows]}


@router.get("/{customer_id}/tickets")
async def get_customer_tickets(customer_id: str):
    """客户工单：通过 contact 里含手机号匹配。"""
    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        rows = s.execute(
            select(Ticket).where(Ticket.contact.like(f"%{c.phone}%")).order_by(Ticket.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [t.to_dict() for t in rows]}


@router.get("/{customer_id}/refunds")
async def get_customer_refunds(customer_id: str):
    with session_scope() as s:
        rows = s.execute(
            select(RefundRequest).where(RefundRequest.customer_id == customer_id).order_by(RefundRequest.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [r.to_dict() for r in rows]}


@router.get("/{customer_id}/risk")
async def get_customer_risk(customer_id: str):
    from app.services.risk_service import check_risk
    return check_risk(customer_id)
