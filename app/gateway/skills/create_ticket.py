
"""OpenClaw Skill：创建工单。"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

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


def create_ticket(
    device_model: str,
    error_code: str,
    description: str = "",
    contact: str = "",
    address: str = "",
) -> Dict[str, Any]:
    tid = f"T{uuid4().hex[:8].upper()}"
    assigned = assign_engineer(error_code)
    return {
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


SCHEMA = {
    "name": "create_ticket",
    "description": "创建售后工单并自动分派工程师",
    "parameters": {
        "type": "object",
        "properties": {
            "device_model": {"type": "string"},
            "error_code": {"type": "string"},
            "description": {"type": "string"},
            "contact": {"type": "string"},
            "address": {"type": "string"},
        },
        "required": ["device_model", "error_code"],
    },
}
