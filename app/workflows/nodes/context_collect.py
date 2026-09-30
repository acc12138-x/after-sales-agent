"""上下文收集节点：根据意图+槽位，从业务服务拉取上下文。"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.facade import get_services
from app.workflows.state import AgentState


CONTEXT_INTENTS = {
    "return", "exchange",
    "warranty", "invoice", "order_query", "logistics",
}

# 这些意图必须有订单号才能继续
NEED_ORDER_INTENTS = {"return", "exchange", "invoice"}


def _collect_order(svc, slots: Dict) -> Optional[Dict]:
    order_id = slots.get("order_id")
    phone = slots.get("phone")
    if order_id:
        return svc.order.get_order(order_id)
    if phone:
        for uid in ["U1001", "U1002"]:
            c = svc.customer.get_customer(uid)
            if c and c.get("phone") == phone:
                orders = svc.order.get_user_orders(uid)
                if orders:
                    return orders[0]
    return None


def _collect_context(intent: str, slots: Dict) -> Dict[str, Any]:
    svc = get_services()
    ctx: Dict[str, Any] = {}
    errors: list = []

    try:
        order = _collect_order(svc, slots)
    except Exception as e:
        order = None
        errors.append(f"order: {e}")

    if order:
        ctx["order"] = order
        ctx["order_id"] = order.get("order_id")
        ctx["user_id"] = order.get("user_id")
        if order.get("delivered_at"):
            try:
                delivered = datetime.fromisoformat(order["delivered_at"])
                ctx["days_since_received"] = (datetime.now() - delivered).days
            except Exception:
                pass
        if order.get("created_at"):
            try:
                created = datetime.fromisoformat(order["created_at"])
                ctx["days_since_purchase"] = (datetime.now() - created).days
            except Exception:
                pass
        items = order.get("items") or []
        if items:
            sku = items[0].get("sku")
            ctx["sku"] = sku
            try:
                prod = svc.product.get_product(sku)
                if prod:
                    ctx["product"] = prod
                    ctx["category"] = prod.get("category")
                    ctx["warranty_days"] = prod.get("warranty_days")
                    if ctx.get("days_since_purchase") is not None:
                        ctx["in_warranty"] = ctx["days_since_purchase"] <= ctx["warranty_days"]
            except Exception as e:
                errors.append(f"product: {e}")
            try:
                ctx["is_special_category"] = svc.product.is_special_category(sku)
            except Exception:
                pass

    if intent == "logistics" and ctx.get("order_id"):
        try:
            logi = svc.logistics.get_tracking(ctx["order_id"])
            if logi:
                ctx["logistics"] = logi
        except Exception as e:
            errors.append(f"logistics: {e}")

    if ctx.get("user_id"):
        try:
            cust = svc.customer.get_customer(ctx["user_id"])
            if cust:
                ctx["customer"] = cust
                ctx["is_vip"] = bool(cust.get("vip"))
        except Exception as e:
            errors.append(f"customer: {e}")

    if slots.get("error_code"):
        ctx["error_code"] = slots["error_code"]
    if slots.get("device_model"):
        ctx["device_model"] = slots["device_model"]

    ctx.setdefault("used", False)
    ctx.setdefault("quality_issue", False)
    ctx.setdefault("has_original_package", True)
    ctx.setdefault("human_damage", False)

    return {"context": ctx, "context_errors": errors}


def context_collect_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "")
    if intent not in CONTEXT_INTENTS:
        return state

    slots = state.get("slots", {}) or {}

    # 必须订单号的意图：如果没有订单号也没手机号，直接追问
    if intent in NEED_ORDER_INTENTS and not slots.get("order_id") and not slots.get("phone"):
        return {
            **state,
            "answer": "请提供订单号或下单手机号，我帮您核实。",
            "missing_slots": ["order_id"],
            "flow_status": "waiting",
        }

    result = _collect_context(intent, slots)
    return {**state, **result}
