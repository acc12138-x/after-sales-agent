
from __future__ import annotations
from datetime import datetime
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.api.schemas.models import TicketCreateRequest, TicketResponse

router = APIRouter(prefix="/tickets", tags=["tickets"])

# 内存存储，后续换 MySQL
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


@router.post("", response_model=TicketResponse)
async def create_ticket(req: TicketCreateRequest) -> TicketResponse:
    tid = f"T{uuid4().hex[:8].upper()}"
    assigned = assign_engineer(req.error_code)
    _TICKETS[tid] = {
        "ticket_id": tid,
        "status": "assigned",
        "assigned_to": assigned,
        "device_model": req.device_model,
        "error_code": req.error_code,
        "description": req.description,
        "contact": req.contact,
        "address": req.address,
        "created_at": datetime.utcnow().isoformat(),
    }
    return TicketResponse(
        ticket_id=tid,
        status="assigned",
        assigned_to=assigned,
        created_at=_TICKETS[tid]["created_at"],
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
async def list_tickets():
    return {"total": len(_TICKETS), "items": list(_TICKETS.values())}
