from __future__ import annotations
from datetime import datetime
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas.models import TicketCreateRequest, TicketResponse
from app.db.models.ticket import Ticket
from app.db.session import session_scope

router = APIRouter(prefix="/tickets", tags=["tickets"])

ENGINEERS = [
    {"name": "张工", "skills": ["E1", "E2", "E102"], "region": "华东"},
    {"name": "李工", "skills": ["E2", "E3"], "region": "华南"},
    {"name": "王工", "skills": ["E102", "E200"], "region": "华北"},
]


def assign_engineer(error_code: str) -> str:
    for e in ENGINEERS:
        if error_code in e["skills"]:
            return e["name"]
    return ENGINEERS[0]["name"]


def do_create_ticket(
    device_model: str,
    error_code: str,
    description: str = "",
    contact: str = "",
    address: str = "",
) -> dict:
    """核心建单逻辑：写 MySQL。"""
    tid = f"T{uuid4().hex[:8].upper()}"
    assigned = assign_engineer(error_code)

    with session_scope() as s:
        t = Ticket(
            ticket_id=tid,
            status="assigned",
            assigned_to=assigned,
            device_model=device_model,
            error_code=error_code,
            description=description,
            contact=contact,
            address=address,
            created_at=datetime.utcnow(),
        )
        s.add(t)
        s.flush()
        return t.to_dict()


@router.post("", response_model=TicketResponse)
async def create_ticket(req: TicketCreateRequest) -> TicketResponse:
    t = do_create_ticket(
        device_model=req.device_model,
        error_code=req.error_code,
        description=req.description,
        contact=req.contact,
        address=req.address,
    )
    return TicketResponse(
        ticket_id=t["ticket_id"],
        status=t["status"],
        assigned_to=t["assigned_to"],
        created_at=t["created_at"],
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str) -> TicketResponse:
    with session_scope() as s:
        t = s.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        return TicketResponse(
            ticket_id=t.ticket_id,
            status=t.status,
            assigned_to=t.assigned_to,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )


@router.get("")
async def list_all_tickets():
    with session_scope() as s:
        rows = s.execute(select(Ticket).order_by(Ticket.created_at.desc())).scalars().all()
        items = [t.to_dict() for t in rows]
    return {"total": len(items), "items": items}
