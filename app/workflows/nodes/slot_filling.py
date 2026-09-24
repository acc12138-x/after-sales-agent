
from __future__ import annotations
from typing import Dict, List

from app.workflows.state import AgentState

REQUIRED_FOR_TICKET = ["device_model", "error_code"]
REQUIRED_FOR_ORDER = ["phone"]


def check_missing(intent: str, slots: Dict) -> List[str]:
    if intent == "ticket":
        return [k for k in REQUIRED_FOR_TICKET if k not in slots or not slots[k]]
    if intent == "order":
        return [k for k in REQUIRED_FOR_ORDER if k not in slots or not slots[k]]
    return []


def slot_filling_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "qa")
    slots = state.get("slots", {}) or {}
    missing = check_missing(intent, slots)

    if missing:
        ask = "请补充以下信息：" + "、".join(missing)
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": ask}]
        return {
            **state,
            "missing_slots": missing,
            "messages": messages,
            "flow_status": "waiting",
        }

    return {**state, "missing_slots": []}
