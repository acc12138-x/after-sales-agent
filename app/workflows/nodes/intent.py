
from __future__ import annotations
import re
from typing import Dict

from app.workflows.state import AgentState

RULES = [
    ("ticket",    [r"报修", r"报障", r"修一下", r"坏了", r"故障", r"创建工单", r"建单"]),
    ("order",     [r"订单", r"物流", r"发货", r"退货", r"换货", r"退款"]),
    ("complaint", [r"投诉", r"差评", r"太差", r"不满意"]),
    ("human",     [r"转人工", r"人工客服", r"找人"]),
]

SLOT_KEYWORDS = {
    "device_model": [r"([A-Z]{1,4}\d{2,5})", r"型号[：: ]*([A-Za-z0-9\-]+)"],
    "error_code":   [r"([Ee]\d{2,4})"],
    "phone":        [r"(1[3-9]\d{9})"],
    "address":      [r"(地址[：: ].+)"],
}


def _extract_slots(text: str) -> Dict:
    slots: Dict = {}
    for key, patterns in SLOT_KEYWORDS.items():
        for p in patterns:
            m = re.search(p, text)
            if m:
                slots[key] = m.group(1) if m.groups() else m.group(0)
                break
    return slots


def detect_intent(text: str) -> str:
    for intent, patterns in RULES:
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return intent
    return "qa"


def intent_node(state: AgentState) -> AgentState:
    text = state.get("user_input", "")
    intent = detect_intent(text)
    slots = state.get("slots", {}) or {}
    slots.update(_extract_slots(text))

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "user", "content": text}]

    return {
        **state,
        "intent": intent,
        "slots": slots,
        "messages": messages,
        "flow_status": "running",
    }
