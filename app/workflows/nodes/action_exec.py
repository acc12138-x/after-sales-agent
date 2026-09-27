"""动作执行节点：根据规则建议的动作，生成用户可见的响应。

高风险动作（need_human=True）会走 hitl_gate。
低风险动作（查物流、查订单等）直接返回结果。
"""
from __future__ import annotations
from typing import Any, Dict

from app.workflows.state import AgentState


ACTION_HANDLERS = {
    "create_return_order": lambda ctx, msg: (
        f"【退货方案】\n{msg}\n\n"
        f"订单号：{ctx.get('order_id', 'N/A')}\n"
        f"商品：{ctx.get('sku', 'N/A')}\n"
        f"如果您确认，我将为您创建退货单。"
    ),
    "create_repair_order": lambda ctx, msg: (
        f"【维修方案】\n{msg}\n\n"
        f"设备：{ctx.get('device_model', 'N/A')}\n"
        f"故障码：{ctx.get('error_code', 'N/A')}\n"
        f"如确认，我将为您预约维修。"
    ),
    "notify_human": lambda ctx, msg: (
        f"【转人工】\n{msg}"
    ),
}


def _build_answer(action: str, ctx: Dict[str, Any], rule_msg: str) -> str:
    handler = ACTION_HANDLERS.get(action)
    if handler:
        return handler(ctx, rule_msg)
    return rule_msg or "已收到您的请求。"


def action_exec_node(state: AgentState) -> AgentState:
    action = state.get("rule_next_action")
    ctx = state.get("context", {}) or {}
    rule_msg = state.get("rule_message", "")

    # 无规则建议动作 → 走通用回答（若已有 answer 就保留）
    if not action:
        return state

    answer = _build_answer(action, ctx, rule_msg)

    # 判断是否需要人工
    matches = state.get("rule_matches", []) or []
    top_result = matches[0]["result"] if matches else {}
    need_human = bool(top_result.get("need_human", False))

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "action": action,
        "action_result": {"action": action, "need_human": need_human},
        "messages": messages,
        "flow_status": "waiting" if need_human else "succeeded",
    }
