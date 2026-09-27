"""意图识别节点：使用可复用的 IntentEngine。"""
from __future__ import annotations
import re
from typing import Dict

from app.intent.factory import get_intent_engine
from app.workflows.state import AgentState

# 槽位抽取规则（顺序重要：先精确，后宽泛）
SLOT_PATTERNS = {
    "order_id": [r"([Oo]\d{8,20})"],                        # 订单号优先
    "phone":    [r"(1[3-9]\d{9})"],
    "error_code": [r"\b([Ee]\d{2,4})\b"],                    # 单字母+2~4数字
    "device_model": [
        r"\b([A-Z]{2,4}\d{2,5})\b",                        # 至少两个大写字母（排除 O202...）
        r"型号[：: ]*([A-Za-z0-9\-]{2,20})",
    ],
    "address": [r"(地址[：: ].+)"],
}


def _extract_slots(text: str) -> Dict:
    slots: Dict = {}
    for key, patterns in SLOT_PATTERNS.items():
        for p in patterns:
            m = re.search(p, text)
            if m:
                val = m.group(1) if m.groups() else m.group(0)
                # 避免把订单号错当设备型号
                if key == "device_model" and val and val.startswith(("O", "o")) and val[1:].isdigit():
                    continue
                slots[key] = val
                break
    return slots


def detect_intent(text: str) -> str:
    engine = get_intent_engine()
    top = engine.classify_top(text)
    return top.id if top else "qa"


def intent_node(state: AgentState) -> AgentState:
    text = state.get("user_input", "")
    engine = get_intent_engine()
    top = engine.classify_top(text)
    intent_id = top.id if top else "qa"

    slots = state.get("slots", {}) or {}
    slots.update(_extract_slots(text))

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "user", "content": text}]

    return {
        **state,
        "intent": intent_id,
        "slots": slots,
        "messages": messages,
        "flow_status": "running",
    }
