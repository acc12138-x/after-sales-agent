"""建单节点：缺关键字段则追问；建单后校验故障码。"""
from __future__ import annotations
from typing import Any, Dict

from app.api.routes.tickets import do_create_ticket
from app.services.code_validator import build_warning, validate_code
from app.workflows.state import AgentState


def ticket_node(state: AgentState) -> AgentState:
    slots: Dict[str, Any] = state.get("slots", {}) or {}
    user_input = state.get("user_input", "")

    device_model = (slots.get("device_model") or "").strip()
    error_code = (slots.get("error_code") or "").strip()
    urgent = any(kw in user_input for kw in ["加急", "急单", "紧急"])

    # 都缺失 → 追问
    if not device_model and not error_code:
        answer = "请提供**设备型号**或**故障码**（例如 E102 / XY200），我才能为您建单。"
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": answer}]
        return {
            **state, "answer": answer,
            "missing_slots": ["device_model", "error_code"],
            "messages": messages, "flow_status": "waiting",
        }

    # ============================================================
    # 故障码校验
    # ============================================================
    code_to_check = error_code or device_model
    validation = validate_code(code_to_check)

    # 建单
    try:
        result = do_create_ticket(
            device_model=device_model or None,
            error_code=error_code or None,
            description=user_input,
            urgent=urgent,
            code_verified=validation.get("known", True),
        )
        tid = result.get("ticket_id", "UNKNOWN")
        assigned = result.get("assigned_to", "工程师")
        is_complete = result.get("is_complete", True)
        missing = result.get("missing_fields", [])

        answer = f"✅ 已为您创建工单 **{tid}**\n"
        answer += f"- 设备型号：{device_model or '待补充'}\n"
        answer += f"- 故障代码：{error_code or '待补充'}\n"
        answer += f"- 已分派给：{assigned}\n"

        if not is_complete:
            answer += f"\n⚠️ 待补充：**{', '.join(missing)}**。\n"

        # 故障码校验警告
        if not validation.get("known"):
            answer += "\n" + build_warning(code_to_check, validation)

        # 保存到 state（供后台审核）
        result["_validation"] = validation

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
