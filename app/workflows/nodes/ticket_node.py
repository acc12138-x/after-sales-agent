
from __future__ import annotations
from typing import Any, Dict

from app.api.routes.tickets import do_create_ticket
from app.workflows.state import AgentState


def ticket_node(state: AgentState) -> AgentState:
    slots: Dict[str, Any] = state.get("slots", {}) or {}
    user_input = state.get("user_input", "")

    device_model = slots.get("device_model") or "未知型号"
    error_code = slots.get("error_code") or "未知故障"

    try:
        result = do_create_ticket(
            device_model=device_model,
            error_code=error_code,
            description=user_input,
        )
        tid = result.get("ticket_id", "UNKNOWN")
        assigned = result.get("assigned_to", "工程师")
        answer = (
            f"✅ 已为您创建工单 **{tid}**\n"
            f"- 设备型号：{device_model}\n"
            f"- 故障代码：{error_code}\n"
            f"- 已分派给：{assigned}\n\n"
            f"稍后 {assigned} 会与您联系确认。"
        )
    except Exception as e:
        result = {"error": str(e)}
        answer = f"建单失败：{e}"

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "tool_result": result,
        "messages": messages,
        "flow_status": "succeeded",
    }
