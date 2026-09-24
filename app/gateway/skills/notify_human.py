
"""OpenClaw Skill：转人工。"""
from __future__ import annotations
from typing import Any, Dict


def notify_human(thread_id: str, reason: str = "") -> Dict[str, Any]:
    return {
        "thread_id": thread_id,
        "reason": reason,
        "status": "queued",
        "message": "已转人工，请等待客服接入",
    }


SCHEMA = {
    "name": "notify_human",
    "description": "转人工客服",
    "parameters": {
        "type": "object",
        "properties": {
            "thread_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["thread_id"],
    },
}
