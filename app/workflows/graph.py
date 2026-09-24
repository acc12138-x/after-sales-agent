
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.workflows.state import AgentState
from app.workflows.nodes.intent import intent_node
from app.workflows.nodes.slot_filling import slot_filling_node
from app.workflows.nodes.rag_search import rag_search_node
from app.workflows.nodes.generate import generate_node
from app.workflows.nodes.hitl_gate import hitl_gate_node


def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "qa")
    if intent == "human":
        return "human"
    return "slot_filling"


def route_after_slot(state: AgentState) -> str:
    if state.get("missing_slots"):
        return "end"
    return "rag_search"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("intent", intent_node)
    g.add_node("slot_filling", slot_filling_node)
    g.add_node("rag_search", rag_search_node)
    g.add_node("generate", generate_node)
    g.add_node("hitl_gate", hitl_gate_node)

    g.set_entry_point("intent")

    g.add_conditional_edges(
        "intent",
        route_after_intent,
        {"slot_filling": "slot_filling", "human": "hitl_gate"},
    )

    g.add_conditional_edges(
        "slot_filling",
        route_after_slot,
        {"rag_search": "rag_search", "end": END},
    )

    g.add_edge("rag_search", "generate")
    g.add_edge("generate", "hitl_gate")
    g.add_edge("hitl_gate", END)

    return g


# 全局 checkpointer，支持 HITL 中断恢复
memory = MemorySaver()
graph = build_graph().compile(checkpointer=memory)
