"""意图识别节点：使用可复用的 IntentEngine。"""
from __future__ import annotations
import re
from typing import Dict

from app.intent.factory import get_intent_engine
from app.workflows.state import AgentState

# 槽位抽取（顺序重要）
ORDER_ID_RE = re.compile(r"([Oo]\d{8,20})")
PHONE_RE = re.compile(r"(1[3-9]\d{9})")
ERROR_CODE_RE = re.compile(r"\b([Ee]\d{2,4})\b")
# 宽松匹配：1-4 个大写字母 + 2-5 位数字（E102 / XY200 / ABC123 都行）
DEVICE_MODEL_RE = re.compile(r"\b([A-Z]{1,4}\d{2,5})\b")
DEVICE_MODEL_CN_RE = re.compile(r"型号[：: ]*([A-Za-z0-9\-]{2,20})")
ADDRESS_RE = re.compile(r"(地址[：: ].+)")


def _extract_slots(text: str) -> Dict:
    """提取槽位，先抽 order_id 并从文本里剔掉，避免误判 device_model。"""
    slots: Dict = {}
    remaining = text

    # 1) order_id（优先）
    m = ORDER_ID_RE.search(remaining)
    if m:
        slots["order_id"] = m.group(1)
        # 从文本里剔掉订单号，避免 O20260101001 被识别成设备型号
        remaining = remaining.replace(m.group(0), " ")

    # 2) phone
    m = PHONE_RE.search(remaining)
    if m:
        slots["phone"] = m.group(1)

    # 3) error_code（E102 等）
    m = ERROR_CODE_RE.search(remaining)
    if m:
        slots["error_code"] = m.group(1).upper()

    # 4) device_model：先中文"型号XXX"，否则通用大写字母+数字
    m = DEVICE_MODEL_CN_RE.search(remaining)
    if m:
        slots["device_model"] = m.group(1)
    else:
        m = DEVICE_MODEL_RE.search(remaining)
        if m:
            candidate = m.group(1)
            # 排除 O 开头的订单号残留
            if not (candidate.startswith(("O", "o")) and candidate[1:].isdigit()):
                slots["device_model"] = candidate

    # 5) address
    m = ADDRESS_RE.search(remaining)
    if m:
        slots["address"] = m.group(1)

    # 6) 特殊规则：error_code 存在且 device_model 缺失时，用 error_code 兜底
    if "error_code" in slots and "device_model" not in slots:
        # E102 这种可能是故障码也可能是设备型号，两个都填
        slots["device_model"] = slots["error_code"]

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
