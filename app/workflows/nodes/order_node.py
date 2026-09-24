
from __future__ import annotations
from typing import Any, Dict

from app.gateway.skills.query_order import query_order
from app.workflows.state import AgentState


def order_node(state: AgentState) -> AgentState:
    """查订单：调用 query_order skill，构造答案。"""
    slots: Dict[str, Any] = state.get("slots", {}) or {}
    phone = slots.get("phone", "")

    if not phone:
        answer = "请提供您的手机号，我帮您查询订单。"
        return {
            **state,
            "answer": answer,
            "missing_slots": ["phone"],
            "flow_status": "waiting",
        }

    try:
        result = query_order(phone)
        if result.get("found"):
            answer = (
                f"订单号：{result.get('order_id')}\n"
                f"当前状态：{result.get('status')}\n"
                f"预计到达：{result.get('eta', '未知')}"
            )
        else:
            answer = result.get("message", "未找到订单，请核对手机号。")
    except Exception as e:
        result = {"error": str(e)}
        answer = f"查询失败：{e}"

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "tool_result": result,
        "messages": messages,
        "flow_status": "succeeded",
    }
