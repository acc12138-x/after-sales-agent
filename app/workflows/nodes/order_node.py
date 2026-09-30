"""订单/物流/客户查询节点（支持单条和多条）。"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.models.customer import Customer
from app.db.models.order import Order
from app.db.session import session_scope
from app.workflows.state import AgentState


def _find_customer_by_phone(phone: str) -> Optional[dict]:
    with session_scope() as s:
        c = s.execute(select(Customer).where(Customer.phone == phone)).scalar_one_or_none()
        return c.to_dict() if c else None


def _find_orders_by_customer(customer_id: str) -> List[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
        ).scalars().all()
        return [o.to_dict() for o in rows]


def _find_order(order_id: str) -> Optional[dict]:
    with session_scope() as s:
        o = s.execute(select(Order).where(Order.order_id == order_id)).scalar_one_or_none()
        return o.to_dict() if o else None


def _format_orders(orders: List[dict], customer: Optional[dict] = None) -> str:
    if not orders:
        return "没有找到相关订单。"
    lines = []
    if customer:
        lines.append(f"👤 **{customer.get('name', '客户')}**（{customer.get('phone')}）")
        lines.append(f"VIP：{customer.get('vip_level', 'normal')} · 共 {len(orders)} 个订单")
        lines.append("")
    for i, o in enumerate(orders, 1):
        warranty = "✅ 在保" if o.get("in_warranty") else "已过保"
        lines.append(
            f"{i}. **{o['order_id']}** — {o.get('product_name', '')}  "
            f"¥{o.get('amount')}  [{o.get('status')}]  {warranty}"
        )
    return "\n".join(lines)


def _format_logistics(logi: dict) -> str:
    events = logi.get("events") or []
    lines = [f"  - {e.get('time', '')}: {e.get('desc', '')}" for e in events[-3:]]
    return (
        f"物流公司：{logi.get('carrier')}\n"
        f"运单号：{logi.get('tracking_no')}\n"
        f"状态：{logi.get('status')}\n"
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

    # 都没提供 → 追问
    if not order_id and not phone:
        answer = "请提供**订单号**或**下单手机号**，我帮您查询。"
        return {
            **state,
            "answer": answer,
            "missing_slots": ["order_id"],
            "flow_status": "waiting",
        }

    # ============================================================
    # 场景 A：按手机号查客户所有订单
    # ============================================================
    if phone and not order_id:
        customer = _find_customer_by_phone(phone)
        if not customer:
            answer = f"未找到手机号 **{phone}** 对应的客户。"
        else:
            orders = _find_orders_by_customer(customer["customer_id"])
            answer = _format_orders(orders, customer)

        messages = state.get("messages", []) or []
        messages = messages + [{"role": "assistant", "content": answer}]
        return {
            **state,
            "answer": answer,
            "messages": messages,
            "flow_status": "succeeded",
        }

    # ============================================================
    # 场景 B：按订单号查
    # ============================================================
    order = _find_order(order_id)
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

    # 物流意图 → 返回物流
    if intent == "logistics":
        from app.services.facade import get_services
        svc = get_services()
        try:
            logi = svc.logistics.get_tracking(order["order_id"])
            answer = _format_logistics(logi) if logi else f"订单 {order_id} 暂无物流信息"
        except Exception:
            answer = f"订单 {order_id} 暂无物流信息"
    else:
        # 单条订单
        answer = _format_orders([order])

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "messages": messages,
        "flow_status": "succeeded",
    }
