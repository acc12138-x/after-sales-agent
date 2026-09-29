from __future__ import annotations

from langgraph.types import interrupt

from app.workflows.state import AgentState

CONFIDENCE_THRESHOLD = 0.5
HIGH_RISK_INTENTS = {"human", "complaint"}
HIGH_RISK_TOOLS = {"refund", "reassign"}
SKIP_CONFIDENCE_INTENTS = {"ticket", "order_query", "logistics", "engineer_query"}


def need_hitl(state: AgentState) -> bool:
    intent = state.get("intent", "")
    if intent in SKIP_CONFIDENCE_INTENTS:
        return False
    if intent in HIGH_RISK_INTENTS:
        return True
    if state.get("tool_name") in HIGH_RISK_TOOLS:
        return True
    if state.get("flow_status") == "rejected":
        return False
    if state.get("confidence", 1.0) < CONFIDENCE_THRESHOLD:
        return True
    return False


def _is_approve(decision) -> bool:
    s = str(decision or "").lower()
    return ("approve" in s) or (s in ("是", "对", "ok", "okay", "yes", "y"))


def hitl_gate_node(state: AgentState) -> AgentState:
    trace = state.get("trace_id", "?")[:8]
    need = need_hitl(state)
    print(f"[HITL:{trace}] need_hitl={need} intent={state.get('intent')} hitl_pending={state.get('hitl_pending')}")
    if not need_hitl(state):
        return {
            **state,
            "hitl_pending": False,
            "flow_status": state.get("flow_status", "succeeded"),
        }

    reason = state.get("hitl_reason") or "需要人工确认"
    intent = state.get("intent", "")

    decision = interrupt({
        "type": "hitl",
        "reason": reason,
        "intent": intent,
        "user_input": state.get("user_input"),
        "allowed": ["approve", "block_revise: <原因>"],
    })

    decision_str = str(decision)
    messages = state.get("messages", []) or []

    if _is_approve(decision):
        if intent == "human":
            new_answer = "✅ 已确认转人工，客服稍后接入。"
        elif intent == "complaint":
            new_answer = "✅ 已受理您的投诉，客服将在 24 小时内与您联系。"
        else:
            new_answer = "✅ 已确认。\n\n" + (state.get("answer") or "")
        flow = "succeeded"
    else:
        new_answer = f"❌ 已取消：{decision_str}"
        flow = "cancelled"

    messages = messages + [{"role": "assistant", "content": new_answer}]

    return {
        **state,
        "answer": new_answer,
        "hitl_pending": False,
        "hitl_decision": decision_str,
        "messages": messages,
        "flow_status": flow,
    }
