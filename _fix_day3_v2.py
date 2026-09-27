import os, subprocess, re
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
VENV_PY = r"I:\XMWJ\PYxm\venvs\easkb-agent\Scripts\python.exe"

W = lambda p, c: open(p, "w", encoding="utf-8", newline="\n").write(c)

# ============================================================
# 修复1：.env 切回 Qwen3-4B
# ============================================================
for fname in [".env", ".env.example"]:
    if not os.path.exists(fname):
        continue
    with open(fname, encoding="utf-8") as f:
        s = f.read()
    s = re.sub(
        r"^OLLAMA_LLM_MODEL=.*$",
        "OLLAMA_LLM_MODEL=modelscope.cn/Qwen/Qwen3-4B-GGUF:latest",
        s, flags=re.MULTILINE
    )
    with open(fname, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    print(f"[OK] {fname} -> Qwen3-4B")

# ============================================================
# 修复2：order_node 支持 order_id 直查
# ============================================================
W("app/workflows/nodes/order_node.py", '''"""订单/物流查询节点：优先用 order_id，无则用 phone，都没有则追问。"""
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
        f"订单号：{order.get('order_id')}\\n"
        f"状态：{order.get('status')}\\n"
        f"金额：{order.get('amount')} 元\\n"
        f"商品：{item_desc}\\n"
        f"下单时间：{order.get('created_at')}"
    )


def _format_logistics(logi: Dict) -> str:
    events = logi.get("events") or []
    lines = [f"  - {e.get('time', '')}: {e.get('desc', '')}" for e in events[-3:]]
    return (
        f"物流公司：{logi.get('carrier')}\\n"
        f"运单号：{logi.get('tracking_no')}\\n"
        f"当前状态：{logi.get('status')}\\n"
        f"当前位置：{logi.get('current_location')}\\n"
        f"预计到达：{logi.get('eta')}\\n"
        f"最近轨迹：\\n" + "\\n".join(lines)
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
            answer = f"订单 {order['order_id']} 暂无物流信息。\\n" + _format_order(order)
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
''')
print("[OK] order_node.py 修复（支持 order_id 直查）")

# ============================================================
# 修复3：context_collect 支持"缺订单号追问"
# ============================================================
W("app/workflows/nodes/context_collect.py", '''"""上下文收集节点：根据意图+槽位，从业务服务拉取上下文。"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.facade import get_services
from app.workflows.state import AgentState


CONTEXT_INTENTS = {
    "return", "exchange", "refund", "repair",
    "warranty", "invoice", "order_query", "logistics",
}

# 这些意图必须有订单号才能继续
NEED_ORDER_INTENTS = {"return", "exchange", "refund", "invoice"}


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
''')
print("[OK] context_collect.py 修复（缺订单号追问）")

# ============================================================
# 修复4：graph.py route_after_context 处理 waiting 场景
# ============================================================
W("app/workflows/graph.py", '''from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.workflows.state import AgentState
from app.workflows.nodes.intent import intent_node
from app.workflows.nodes.slot_filling import slot_filling_node
from app.workflows.nodes.context_collect import context_collect_node
from app.workflows.nodes.rule_match import rule_match_node
from app.workflows.nodes.rag_search import rag_search_node
from app.workflows.nodes.generate import generate_node
from app.workflows.nodes.hitl_gate import hitl_gate_node
from app.workflows.nodes.ticket_node import ticket_node
from app.workflows.nodes.order_node import order_node
from app.workflows.nodes.action_exec import action_exec_node


RULE_INTENTS = {"return", "exchange", "refund", "warranty", "repair"}
QUERY_INTENTS = {"order_query", "logistics"}


def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "qa")
    if intent == "human":
        return "hitl_gate"
    return "slot_filling"


def route_after_slot(state: AgentState) -> str:
    if state.get("missing_slots"):
        return "end"
    intent = state.get("intent", "qa")
    if intent in RULE_INTENTS:
        return "context_collect"
    if intent in QUERY_INTENTS:
        return "context_collect"
    if intent == "ticket":
        return "ticket_node"
    return "rag_search"


def route_after_context(state: AgentState) -> str:
    # 缺信息追问 -> 直接结束
    if state.get("flow_status") == "waiting" and state.get("missing_slots"):
        return "end"
    intent = state.get("intent", "")
    if intent in QUERY_INTENTS:
        return "order_node"
    return "rule_match"


def route_after_rule(state: AgentState) -> str:
    if state.get("rule_matches"):
        return "action_exec"
    return "rag_search"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("intent", intent_node)
    g.add_node("slot_filling", slot_filling_node)
    g.add_node("context_collect", context_collect_node)
    g.add_node("rule_match", rule_match_node)
    g.add_node("rag_search", rag_search_node)
    g.add_node("generate", generate_node)
    g.add_node("hitl_gate", hitl_gate_node)
    g.add_node("ticket_node", ticket_node)
    g.add_node("order_node", order_node)
    g.add_node("action_exec", action_exec_node)

    g.set_entry_point("intent")

    g.add_conditional_edges(
        "intent",
        route_after_intent,
        {"slot_filling": "slot_filling", "hitl_gate": "hitl_gate"},
    )

    g.add_conditional_edges(
        "slot_filling",
        route_after_slot,
        {
            "context_collect": "context_collect",
            "ticket_node": "ticket_node",
            "rag_search": "rag_search",
            "end": END,
        },
    )

    g.add_conditional_edges(
        "context_collect",
        route_after_context,
        {"rule_match": "rule_match", "order_node": "order_node", "end": END},
    )

    g.add_conditional_edges(
        "rule_match",
        route_after_rule,
        {"action_exec": "action_exec", "rag_search": "rag_search"},
    )

    g.add_edge("rag_search", "generate")
    g.add_edge("generate", "hitl_gate")

    g.add_edge("action_exec", "hitl_gate")
    g.add_edge("ticket_node", END)
    g.add_edge("order_node", END)
    g.add_edge("hitl_gate", END)

    return g


memory = MemorySaver()
graph = build_graph().compile(checkpointer=memory)
''')
print("[OK] graph.py 修复（waiting 场景短路）")

# ============================================================
# 语法检查
# ============================================================
print()
print("=== 语法检查 ===")
for f in ["app/workflows/nodes/order_node.py",
          "app/workflows/nodes/context_collect.py",
          "app/workflows/graph.py"]:
    r = subprocess.run([VENV_PY, "-m", "py_compile", f],
                       capture_output=True, text=True)
    print(f"[{'OK' if r.returncode==0 else 'ERR'}] {f}")
    if r.returncode != 0:
        print(r.stderr)

# ============================================================
# 重跑测试
# ============================================================
print()
print("=" * 60)
print("重跑工作流 v2 测试（使用 Qwen3-4B）")
print("=" * 60)
os.system(f'"{VENV_PY}" scripts\\test_workflow_v2.py')
