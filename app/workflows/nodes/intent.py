"""意图识别节点：咨询词优先 + 槽位合并 + 多轮上下文。"""
from __future__ import annotations
import re
from typing import Dict, List, Optional

from app.intent.factory import get_intent_engine
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


# ============================================================
# 咨询词（优先级最高）
# ============================================================
CONSULT_PATTERNS = [
    r"是什么", r"为什么",
    r"怎么(办|了|样|回事|排查|处理|解决|操作|做)",
    r"如何(排查|处理|解决|操作|修|做)?",
    # 新增：说明类
    r"适用范围", r"适用",
    r"包含(什么|哪些|哪些内容)?", r"包括(什么|哪些)?",
    r"介绍(一下|一下呗)?", r"说明(一下)?", r"讲讲",
    r"什么意思", r"含义",
    # 疑问
    r"能不能", r"会不会", r"是不是", r"可不可以", r"有没有",
    r"第一[步个]",
    r"请教", r"求教", r"请问",
    r"[吗呢]\s*[？?]?\s*$",
    r"[？?]\s*$",
]

# 明确动作词（优先级 > 咨询词）
ACTION_WORDS = ["帮我", "给我", "我要", "申请", "创建", "建单", "登记", "报修", "预约"]


def _is_consult_query(text: str) -> bool:
    """咨询问句：优先判断，走 RAG。"""
    if not text:
        return False

    # 1. 明确动作词 -> 不算咨询
    for w in ACTION_WORDS:
        if w in text:
            return False

    # 2. 咨询词 -> 咨询
    for pat in CONSULT_PATTERNS:
        if re.search(pat, text):
            return True

    return False


# ============================================================
# 多轮上下文
# ============================================================
FOLLOWUP_KEYWORDS = {
    "ticket": ["设备型号", "故障码", "故障代码", "型号", "设备"],
    "refund_apply": ["订单号", "退款金额", "金额"],
    "order_query": ["订单号或下单手机号", "订单号"],
    "logistics": ["订单号或下单手机号"],
}


def _detect_followup_intent(messages: list) -> Optional[str]:
    if not messages:
        return None
    for m in reversed(messages):
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "")
        if "请提供" in content or "请补充" in content:
            for intent, keywords in FOLLOWUP_KEYWORDS.items():
                if any(kw in content for kw in keywords):
                    return intent
        break
    return None


def _is_pure_slot_input(text: str, slots: dict) -> bool:
    """判断是不是"纯槽位输入"（用于多轮补槽位场景）。

    条件：
    - 短文本（<= 20 字）
    - 有槽位
    - 无业务关键词
    - 意图引擎判断为 qa
    """
    t = text.strip()
    if not t or len(t) > 20:
        return False
    if not slots:
        return False

    engine = get_intent_engine()
    top = engine.classify_top(t)
    if top and top.id not in ("qa",):
        return False

    return True


# ============================================================
# 主节点
# ============================================================
# ============================================================
# 候选确认检测（"您可能是想说 E200，1. E200 / 2. E310"）
# ============================================================
CODE_CAND_PAT = re.compile(r"(\d+)\.\s*\*\*([A-Z]+\d+)\*\*")


def _detect_code_correction(messages: list):
    """检测用户是否在回复候选确认。

    返回 {1: "E200", 2: "E310"} 或 None
    """
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
    """用户回复匹配候选：数字 / 码本身 / 是/对 都接受。"""
    t = text.strip().upper()
    # 数字
    if t.isdigit() and int(t) in mapping:
        return mapping[int(t)]
    # 直接输码
    for code in mapping.values():
        if code.upper() in t:
            return code
    # "是" / "对" / "对，就是这个" → 取第一个
    if t in ("是", "对", "yes", "y") or t.startswith(("对", "是")):
        return list(mapping.values())[0]
    return None


def detect_intent(text: str) -> str:
    engine = get_intent_engine()
    top = engine.classify_top(text)
    return top.id if top else "qa"


def intent_node(state: AgentState) -> AgentState:
    text = state.get("user_input", "")
    messages_history = state.get("messages", []) or []
    old_slots = state.get("slots", {}) or {}

    # ============================================================
    # 候选确认优先：如果上一条 assistant 是"您可能是想说..."
    # ============================================================
    correction_map = _detect_code_correction(messages_history)
    if correction_map:
        corrected = _match_correction(text, correction_map)
        if corrected:
            # 用户确认了候选 → 用修正后的码建单
            new_messages = messages_history + [{"role": "user", "content": text}]
            return {
                **state,
                "intent": "ticket",
                "slots": {"error_code": corrected, "device_model": corrected},
                "messages": new_messages,
                "flow_status": "running",
            }

    new_slots = _extract_slots(text)

    # ============================================================
    # 优先级 1：咨询词 -> 强制 qa
    # ============================================================
    if _is_consult_query(text):
        new_messages = messages_history + [{"role": "user", "content": text}]
        return {
            **state,
            "intent": "qa",
            "slots": {},   # 咨询不需要槽位（避免污染）
            "messages": new_messages,
            "flow_status": "running",
        }

    # ============================================================
    # 优先级 2：判断是否多轮补槽位
    # ============================================================
    followup_intent = _detect_followup_intent(messages_history)
    is_pure_slot = _is_pure_slot_input(text, new_slots)

    if is_pure_slot and followup_intent:
        # 补槽位：合并旧槽位 + 新槽位
        merged_slots = dict(old_slots)
        merged_slots.update(new_slots)
        intent_id = followup_intent
    else:
        # 新对话：只用新槽位（清空旧）
        merged_slots = new_slots
        # 意图引擎判断
        engine = get_intent_engine()
        top = engine.classify_top(text)
        intent_id = top.id if top else "qa"

    new_messages = messages_history + [{"role": "user", "content": text}]

    return {
        **state,
        "intent": intent_id,
        "slots": merged_slots,
        "messages": new_messages,
        "flow_status": "running",
    }
