
from __future__ import annotations

from langgraph.types import interrupt

from app.workflows.state import AgentState

CONFIDENCE_THRESHOLD = 0.6
HIGH_RISK_INTENTS = {"human", "complaint"}
HIGH_RISK_TOOLS = {"refund", "reassign"}


def need_hitl(state: AgentState) -> bool:
    intent = state.get("intent", "")
    if intent in HIGH_RISK_INTENTS:
        return True
    if state.get("tool_name") in HIGH_RISK_TOOLS:
        return True
    if state.get("flow_status") == "rejected":
        return False
    if state.get("confidence", 1.0) < CONFIDENCE_THRESHOLD:
        return True
    return False


def hitl_gate_node(state: AgentState) -> AgentState:
    if not need_hitl(state):
        return {
            **state,
            "hitl_pending": False,
            "flow_status": state.get("flow_status", "succeeded"),
        }

    reason = state.get("hitl_reason") or "需要人工确认"

    # 真正的中断：LangGraph 会暂停，等待 resume 传入 decision
    decision = interrupt({
        "type": "hitl",
        "reason": reason,
        "intent": state.get("intent"),
        "user_input": state.get("user_input"),
        "allowed": ["approve", "block_revise: <原因>"],
    })

    return {
        **state,
        "hitl_pending": False,
        "hitl_decision": str(decision),
        "flow_status": "succeeded",
    }
