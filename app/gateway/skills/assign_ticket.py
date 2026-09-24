
"""OpenClaw Skill：改派工单。"""
from __future__ import annotations
from typing import Any, Dict


def assign_ticket(ticket_id: str, engineer: str, reason: str = "") -> Dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "assigned_to": engineer,
        "reason": reason,
        "status": "reassigned",
        "need_hitl": True,
    }


SCHEMA = {
    "name": "assign_ticket",
    "description": "改派工单给指定工程师（需人工审批）",
    "parameters": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "engineer": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["ticket_id", "engineer"],
    },
}
