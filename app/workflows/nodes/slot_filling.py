"""槽位填充节点：缺关键字段则追问，不硬塞默认值。

规则：
- ticket: device_model 或 error_code 至少一个（不要求两个都有）
- order_query / logistics: 需要 order_id 或 phone 至少一个
"""
from __future__ import annotations
from typing import Dict, List

from app.workflows.state import AgentState


def check_missing(intent: str, slots: Dict) -> List[str]:
    slots = slots or {}

    def _has(k):
        return bool((slots.get(k) or "").strip())

    if intent == "ticket":
        # 至少一个
        if not _has("device_model") and not _has("error_code"):
            return ["device_model_or_error_code"]
        return []

    if intent in ("order_query", "logistics"):
        if not _has("order_id") and not _has("phone"):
            return ["order_id_or_phone"]
        return []

    if intent in ("return", "exchange", "refund", "invoice"):
        if not _has("order_id") and not _has("phone"):
            return ["order_id_or_phone"]
        return []

    return []


PROMPT_MAP = {
    "device_model_or_error_code": "请提供**设备型号**（如 XY200）或**故障码**（如 E102），我才能为您建单。",
    "order_id_or_phone": "请提供**订单号**或**下单手机号**，我帮您查询。",
}


def _format_ask(missing: List[str]) -> str:
    parts = []
    for m in missing:
        parts.append(PROMPT_MAP.get(m, f"请补充：{m}"))
    return "\n\n".join(parts)


def slot_filling_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "qa")
    slots = state.get("slots", {}) or {}
    missing = check_missing(intent, slots)

    if missing:
        ask = _format_ask(missing)
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": ask}]
        return {
            **state,
            "missing_slots": missing,
            "answer": ask,
            "messages": messages,
            "flow_status": "waiting",
        }

    return {**state, "missing_slots": []}
