"""意图识别节点：意图 + 槽位 + 多轮上下文（含动态重载）。"""
from __future__ import annotations
import re
import time
from typing import Dict, List, Optional

from app.intent.factory import get_intent_engine, reload_intent_engine
from app.workflows.state import AgentState

# ---------- 槽位正则 ----------
ORDER_ID_RE = re.compile(r"([Oo]\d{8,20})")
PHONE_RE = re.compile(r"(1[3-9]\d{9})")
ERROR_CODE_RE = re.compile(r"([Ee]\d{2,4})")
DEVICE_MODEL_RE = re.compile(r"([A-Z]{1,4}\d{2,5})")
DEVICE_MODEL_CN_RE = re.compile(r"型号[：: ]*([A-Za-z0-9\-]{2,20})")
ADDRESS_RE = re.compile(r"(地址[：: ].+)")
AMOUNT_RE = re.compile(r"(?:金额|退款|赔付|补偿)[：: ]*([0-9]+(?:\.[0-9]+)?)")
AMOUNT_RE2 = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:元|块)")

# ---------- 意图引擎动态重载 ----------
_engine_reload_ts = 0
_engine_reload_interval = 60  # 每 60 秒检查一次


def _maybe_reload_engine():
    """每 60 秒重载一次，让 yaml 改动生效。"""
    global _engine_reload_ts
    now = time.time()
    if now - _engine_reload_ts > _engine_reload_interval:
        try:
            reload_intent_engine("default")
            _engine_reload_ts = now
        except Exception:
            pass


def _extract_slots(text: str) -> Dict:
    slots: Dict = {}
    remaining = text

    m = ORDER_ID_RE.search(remaining)
    if m:
        slots["order_id"] = m.group(1)
        remaining = remaining.replace(m.group(0), " ")

    m = PHONE_RE.search(remaining)
    if m:
        slots["phone"] = m.group(1)

    m = ERROR_CODE_RE.search(remaining)
    if m:
        slots["error_code"] = m.group(1).upper()

    m = DEVICE_MODEL_CN_RE.search(remaining)
    if m:
        slots["device_model"] = m.group(1)
    else:
        m = DEVICE_MODEL_RE.search(remaining)
        if m:
            candidate = m.group(1)
            if not (candidate.startswith(("O", "o")) and candidate[1:].isdigit()):
                slots["device_model"] = candidate

    m = ADDRESS_RE.search(remaining)
    if m:
        slots["address"] = m.group(1)

    m = AMOUNT_RE.search(remaining) or AMOUNT_RE2.search(remaining)
    if m:
        try:
            slots["amount"] = float(m.group(1))
        except Exception:
            pass

    if re.match(r"^[\s\+\-]*(1[3-9]\d{9})[\s\+\-]*$", remaining.strip()):
        m2 = re.search(r"1[3-9]\d{9}", remaining)
        if m2:
            slots["phone"] = m2.group(0)

    if "error_code" in slots and "device_model" not in slots:
        slots["device_model"] = slots["error_code"]

    return slots


# ---------- 咨询判断 ----------
CONSULT_PATTERNS = [
    r"是什么", r"为什么",
    r"怎么(办|了|样|回事|排查|处理|解决|操作|做)",
    r"如何(排查|处理|解决|操作|修|做)?",
    r"适用范围", r"适用",
    r"包含(什么|哪些|哪些内容)?", r"包括(什么|哪些)?",
    r"介绍(一下|一下呗)?", r"说明(一下)?", r"讲讲",
    r"什么意思", r"含义",
    r"能不能", r"会不会", r"是不是", r"可不可以", r"有没有",
    r"第一[步个]",
    r"请教", r"求教", r"请问",
    r"[吗呢]\s*[？?]?\s*$",
    r"[？?]\s*$",
]

ACTION_WORDS = ["帮我", "给我", "我要", "申请", "创建", "建单", "登记", "报修", "预约"]

BUSINESS_KEYWORDS = [
    "订单", "物流", "快递", "工单", "退款", "退货", "换货",
    "赔付", "补偿", "发票", "保修", "维修", "报修", "客户",
    "手机号", "运单", "发货", "签收", "加急", "急单",
    "工程师", "师傅", "有空", "空闲", "谁在", "负载", "工",
]


def _is_consult_query(text: str) -> bool:
    if not text:
        return False
    # 业务关键词优先
    for w in BUSINESS_KEYWORDS:
        if w in text:
            return False
    # 动作词
    for w in ACTION_WORDS:
        if w in text:
            return False
    # 手机号
    if re.search(r"1[3-9]\d{9}", text):
        return False
    # 纯数字
    if re.match(r"^[\s\+\-\d]{8,20}$", text):
        return False
    # 工程师名
    if re.search(r"[赵张李王孙周吴郑陈刘杨黄胡]工", text):
        return False
    # 咨询模式
    for pat in CONSULT_PATTERNS:
        if re.search(pat, text):
            return True
    return False


# ---------- 多轮上下文 ----------
FOLLOWUP_KEYWORDS = {
    "ticket": ["设备型号", "故障码", "故障代码", "型号"],
    "refund_apply": ["订单号", "退款金额", "金额"],
    "order_query": ["订单号或下单手机号", "订单号"],
    "logistics": ["订单号或下单手机号"],
}


def _detect_followup_intent(messages: list) -> Optional[str]:
    if not messages or len(messages) < 2:
        return None
    # 找最后一条 assistant
    last_assistant = None
    for m in reversed(messages):
        if m.get("role") == "assistant":
            last_assistant = m.get("content", "")
            break
    if not last_assistant:
        return None
    if "请提供" not in last_assistant and "请补充" not in last_assistant:
        return None
    for intent, keywords in FOLLOWUP_KEYWORDS.items():
        if any(kw in last_assistant for kw in keywords):
            return intent
    return None


def _is_pure_slot_input(text: str, new_slots: dict) -> bool:
    """纯槽位输入：短 + 有槽位 + 无业务词。"""
    t = text.strip()
    if not t or len(t) > 30:
        return False
    if not new_slots:
        return False
    # 有业务词就不是纯槽位
    for w in BUSINESS_KEYWORDS + ACTION_WORDS:
        if w in t:
            return False
    return True


# ---------- 候选确认 ----------
CODE_CAND_PAT = re.compile(r"(\d+)\.\s*\*\*([A-Z]+\d+)\*\*")


def _detect_code_correction(messages: list):
    if not messages or len(messages) < 2:
        return None
    last_assistant = None
    for m in reversed(messages):
        if m.get("role") == "assistant":
            last_assistant = m.get("content", "")
            break
    if not last_assistant or "您可能是想说" not in last_assistant:
        return None
    cands = CODE_CAND_PAT.findall(last_assistant)
    if not cands:
        return None
    return {int(i): code for i, code in cands}


def _match_correction(text: str, mapping: dict):
    t = text.strip().upper()
    if t.isdigit() and int(t) in mapping:
        return mapping[int(t)]
    for code in mapping.values():
        if code.upper() in t:
            return code
    if t in ("是", "对", "YES", "Y") or t.startswith(("对", "是")):
        return list(mapping.values())[0]
    return None


# ---------- 主节点 ----------
def detect_intent(text: str) -> str:
    _maybe_reload_engine()
    engine = get_intent_engine()
    top = engine.classify_top(text)
    return top.id if top else "qa"


def intent_node(state: AgentState) -> AgentState:
    _maybe_reload_engine()

    text = state.get("user_input", "")
    messages_history = state.get("messages", []) or []
    old_slots = state.get("slots", {}) or {}

    # 诊断
    print(f"[INTENT] text={text!r} msgs={len(messages_history)}")

    # 1. 候选确认优先
    correction_map = _detect_code_correction(messages_history)
    if correction_map:
        corrected = _match_correction(text, correction_map)
        if corrected:
            new_messages = messages_history + [{"role": "user", "content": text}]
            return {
                **state,
                "intent": "ticket",
                "slots": {"error_code": corrected, "device_model": corrected},
                "messages": new_messages,
                "flow_status": "running",
            }

    # 2. 咨询判断
    if _is_consult_query(text):
        new_messages = messages_history + [{"role": "user", "content": text}]
        return {
            **state,
            "intent": "qa",
            "slots": {},
            "messages": new_messages,
            "flow_status": "running",
        }

    # 3. 提取槽位
    new_slots = _extract_slots(text)

    # 4. 多轮补槽位
    followup_intent = _detect_followup_intent(messages_history)
    is_pure_slot = _is_pure_slot_input(text, new_slots)

    # 5. 意图引擎
    engine = get_intent_engine()
    top = engine.classify_top(text)
    engine_intent = top.id if top else "qa"
    engine_score = top.score if top else 0

    print(f"[INTENT] engine={engine_intent} score={engine_score:.1f} followup={followup_intent} pure_slot={is_pure_slot}")

    # 6. 决策
    if followup_intent and is_pure_slot:
        # 补槽位
        merged_slots = dict(old_slots)
        merged_slots.update(new_slots)
        intent_id = followup_intent
    else:
        merged_slots = new_slots
        intent_id = engine_intent

    new_messages = messages_history + [{"role": "user", "content": text}]

    return {
        **state,
        "intent": intent_id,
        "slots": merged_slots,
        "messages": new_messages,
        "flow_status": "running",
    }
