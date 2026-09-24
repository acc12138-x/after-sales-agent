
from __future__ import annotations
from typing import Annotated, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class AgentState(TypedDict, total=False):
    # 会话
    thread_id: str
    user_input: str
    messages: Annotated[List[Dict], operator.add]

    # 意图与槽位
    intent: str            # qa / ticket / order / complaint / human
    slots: Dict            # 收集到的槽位
    missing_slots: List[str]

    # RAG
    query_rewritten: str
    retrieved: List[Dict]  # 重排后的 chunk
    answer: str
    citations: List[Dict]
    confidence: float

    # 工具调用
    tool_name: Optional[str]
    tool_result: Optional[Dict]

    # HITL
    hitl_pending: bool
    hitl_reason: str
    hitl_decision: Optional[str]

    # 状态
    flow_status: str       # running / waiting / succeeded / failed / rejected
    error: Optional[str]
