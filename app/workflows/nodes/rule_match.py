"""规则匹配节点：根据意图+上下文，用规则引擎匹配规则。"""
from __future__ import annotations
from typing import Any, Dict

from app.rules.core.types import MatchOptions
from app.rules.factory import get_engine
from app.workflows.state import AgentState


# 意图 → 规则 category 映射
INTENT_TO_CATEGORY = {
    "return":      "return",
    "exchange":    "return",
    "refund":      "return",
    "warranty":    "warranty",
    "repair":      "warranty",
    "order_query": None,
    "logistics":   None,
    "invoice":     None,
}


def _to_dict(match) -> Dict[str, Any]:
    """把 RuleMatch 转成可序列化的 dict。"""
    r = match.rule
    return {
        "rule_id": r.id,
        "rule_name": r.name,
        "priority": r.priority,
        "result": dict(r.result),
    }


def rule_match_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "")
    category = INTENT_TO_CATEGORY.get(intent)

    if not category:
        return state

    ctx = state.get("context", {}) or {}
    engine = get_engine("after_sales")

    options = MatchOptions(category=category, stop_on_first=False)
    matches = engine.match(ctx, options)

    if not matches:
        return state

    # 过滤掉默认兜底规则（id=_default_no_match）
    real_matches = [m for m in matches if m.rule.id != "_default_no_match"]
    if not real_matches:
        return state

    top = real_matches[0]
    top_result = top.rule.result or {}

    return {
        **state,
        "rule_matches": [_to_dict(m) for m in real_matches],
        "rule_message": top_result.get("message", ""),
        "rule_next_action": top_result.get("next_action"),
    }
