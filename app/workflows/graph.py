from __future__ import annotations

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
