"""退款申请节点：创建退款单 + AI 初审 + 风控（同步）。"""
from __future__ import annotations
from typing import Any, Dict

from sqlalchemy import select

from app.db.models.order import Order
from app.db.session import session_scope
from app.workflows.state import AgentState


def _query_order(order_id: str) -> dict | None:
    """查订单（同步）。"""
    try:
        with session_scope() as s:
            o = s.execute(select(Order).where(Order.order_id == order_id)).scalar_one_or_none()
            if o is None:
                return None
            return o.to_dict()
    except Exception:
        return None


def refund_apply_node(state: AgentState) -> AgentState:
    slots: Dict[str, Any] = state.get("slots", {}) or {}
    user_input = state.get("user_input", "")

    order_id = (slots.get("order_id") or "").strip()
    amount = slots.get("amount")
    reason = slots.get("reason") or user_input

    # ---------- 缺订单号 → 追问 ----------
    if not order_id:
        answer = "请提供**订单号**，我才能为您创建退款申请。"
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": answer}]
        return {
            **state,
            "answer": answer,
            "missing_slots": ["order_id"],
            "messages": messages,
            "flow_status": "waiting",
        }

    # ---------- 查订单 ----------
    order = _query_order(order_id)
    if not order:
        answer = f"未找到订单 **{order_id}**，请核对订单号。"
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": answer}]
        return {
            **state,
            "answer": answer,
            "messages": messages,
            "flow_status": "succeeded",
        }

    customer_id = order.get("customer_id") or ""
    if not customer_id:
        answer = f"订单 {order_id} 缺少客户信息，无法创建退款单。"
        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": answer}]
        return {
            **state,
            "answer": answer,
            "messages": messages,
            "flow_status": "succeeded",
        }

    # ---------- 缺金额 → 用订单金额 ----------
    if not amount:
        amount = float(order.get("amount", 0))

    # ---------- 创建退款单 ----------
    try:
        from app.api.routes.refunds import do_create_refund
        result = do_create_refund(
            customer_id=customer_id,
            order_id=order_id,
            amount=float(amount),
            refund_type="refund_only",
            reason=reason,
            ticket_id=state.get("thread_id", ""),
        )

        rid = result.get("refund_id", "UNKNOWN")
        status = result.get("status", "")
        ai = result.get("ai_suggestion", "")
        conf = result.get("ai_confidence", 0)
        ai_reason = result.get("ai_reason", "")
        risk = result.get("risk_flag", "")

        if status == "approved":
            answer = f"✅ 退款单 **{rid}** 已自动通过\n"
            answer += f"- 订单：{order_id}\n"
            answer += f"- 金额：¥{amount}\n"
            answer += f"- 客户：{customer_id}\n"
            answer += f"- AI 判断：{ai_reason}\n\n"
            answer += "系统将自动执行退款。"
        else:
            answer = f"📋 退款单 **{rid}** 已创建，**待人工审批**\n"
            answer += f"- 订单：{order_id}\n"
            answer += f"- 金额：¥{amount}\n"
            answer += f"- 客户：{customer_id}\n"
            answer += f"- AI 建议：{ai_reason}\n"
            if risk:
                answer += f"- ⚠️ 风控标记：{risk}\n"
            answer += "\n已通知审批人处理。"

        result_dict = result
    except Exception as e:
        result_dict = {"error": str(e)}
        answer = f"退款单创建失败：{e}"

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "tool_result": result_dict,
        "messages": messages,
        "flow_status": "succeeded",
    }
