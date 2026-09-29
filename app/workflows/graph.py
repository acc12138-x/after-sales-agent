from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

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
from app.workflows.nodes.engineer_query import engineer_query_node
from app.workflows.nodes.action_exec import action_exec_node
from app.workflows.nodes.refund_apply import refund_apply_node


RULE_INTENTS = {"return", "exchange", "warranty", "repair"}
QUERY_INTENTS = {"order_query", "logistics", "customer_query"}
REFUND_INTENTS = {"refund_apply", "compensation"}
HITL_DIRECT_INTENTS = {"human", "complaint"}


def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "qa")
    if intent in HITL_DIRECT_INTENTS:
        return "hitl_gate"
    return "slot_filling"


def route_after_slot(state: AgentState) -> str:
    if state.get("missing_slots"):
        return "end"
    intent = state.get("intent", "qa")
    if intent in RULE_INTENTS:
        return "context_collect"
    if intent == "engineer_query":
        return "engineer_query"
    if intent in QUERY_INTENTS:
        return "context_collect"
    if intent == "ticket":
        return "ticket_node"
    if intent in REFUND_INTENTS:
        return "refund_apply"
    return "rag_search"


def route_after_context(state: AgentState) -> str:
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
    g.add_node("engineer_query", engineer_query_node)
    g.add_node("action_exec", action_exec_node)
    g.add_node("refund_apply", refund_apply_node)

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
            "refund_apply": "refund_apply",
            "engineer_query": "engineer_query",
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
    g.add_edge("refund_apply", END)
    g.add_edge("order_node", END)
    g.add_edge("engineer_query", END)
    g.add_edge("hitl_gate", END)

    return g


# ============================================================
# Checkpointer：SQLite 持久化（跨进程、跨重启保留中断状态）
# ============================================================
_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "checkpoints.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
memory = SqliteSaver(_conn)

graph = build_graph().compile(checkpointer=memory)
