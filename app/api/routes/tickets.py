
from __future__ import annotations
from datetime import datetime
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.api.schemas.models import TicketCreateRequest, TicketResponse

router = APIRouter(prefix="/tickets", tags=["tickets"])

_TICKETS: Dict[str, dict] = {}

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
    """核心建单逻辑，供 API 和 LangGraph node 共享。"""
    tid = f"T{uuid4().hex[:8].upper()}"
    assigned = assign_engineer(error_code)
    ticket = {
        "ticket_id": tid,
        "status": "assigned",
        "assigned_to": assigned,
        "device_model": device_model,
        "error_code": error_code,
        "description": description,
        "contact": contact,
        "address": address,
        "created_at": datetime.utcnow().isoformat(),
    }
    _TICKETS[tid] = ticket
    return ticket


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
    if ticket_id not in _TICKETS:
        raise HTTPException(status_code=404, detail="ticket not found")
    t = _TICKETS[ticket_id]
    return TicketResponse(
        ticket_id=t["ticket_id"],
        status=t["status"],
        assigned_to=t.get("assigned_to"),
        created_at=t["created_at"],
    )


@router.get("")
async def list_all_tickets():
    items = sorted(_TICKETS.values(), key=lambda x: x["created_at"], reverse=True)
    return {"total": len(items), "items": items}
