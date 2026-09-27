"""订单/物流查询节点：优先用 order_id，无则用 phone，都没有则追问。"""
from __future__ import annotations
from typing import Any, Dict, Optional

from app.services.facade import get_services
from app.workflows.state import AgentState


def _find_order(svc, order_id: Optional[str], phone: Optional[str]) -> Optional[Dict]:
    if order_id:
        o = svc.order.get_order(order_id)
        if o:
            return o
    if phone:
        # 按手机号找客户 -> 找订单
        for uid in ["U1001", "U1002"]:
            c = svc.customer.get_customer(uid)
            if c and c.get("phone") == phone:
                orders = svc.order.get_user_orders(uid)
                if orders:
                    return orders[0]
    return None


def _format_order(order: Dict) -> str:
    items = order.get("items") or []
    item_desc = "、".join(f"{i.get('name')} x{i.get('quantity')}" for i in items) or "N/A"
    return (
        f"订单号：{order.get('order_id')}\n"
        f"状态：{order.get('status')}\n"
        f"金额：{order.get('amount')} 元\n"
        f"商品：{item_desc}\n"
        f"下单时间：{order.get('created_at')}"
    )


def _format_logistics(logi: Dict) -> str:
    events = logi.get("events") or []
    lines = [f"  - {e.get('time', '')}: {e.get('desc', '')}" for e in events[-3:]]
    return (
        f"物流公司：{logi.get('carrier')}\n"
        f"运单号：{logi.get('tracking_no')}\n"
        f"当前状态：{logi.get('status')}\n"
        f"当前位置：{logi.get('current_location')}\n"
        f"预计到达：{logi.get('eta')}\n"
        f"最近轨迹：\n" + "\n".join(lines)
    )


def order_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "")
    slots: Dict[str, Any] = state.get("slots", {}) or {}
    ctx: Dict[str, Any] = state.get("context", {}) or {}

    order_id = slots.get("order_id") or ctx.get("order_id")
    phone = slots.get("phone")

    # 都没提供 -> 追问
    if not order_id and not phone:
        answer = "请提供订单号或下单手机号，我帮您查询。"
        return {
            **state,
            "answer": answer,
            "missing_slots": ["order_id"],
            "flow_status": "waiting",
        }

    svc = get_services()
    order = _find_order(svc, order_id, phone)

    if not order:
        return {
            **state,
            "answer": "未找到对应订单，请核对订单号或手机号。",
            "flow_status": "succeeded",
        }

    # 物流意图 -> 返回物流
    if intent == "logistics":
        logi = svc.logistics.get_tracking(order["order_id"])
        if logi:
            answer = _format_logistics(logi)
        else:
            answer = f"订单 {order['order_id']} 暂无物流信息。\n" + _format_order(order)
    else:
        answer = _format_order(order)

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "context": {**ctx, "order": order, "order_id": order["order_id"]},
        "messages": messages,
        "flow_status": "succeeded",
    }
