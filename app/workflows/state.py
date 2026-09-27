from __future__ import annotations
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class AgentState(TypedDict, total=False):
    # 会话
    thread_id: str
    user_input: str
    messages: Annotated[List[Dict], operator.add]

    # 意图与槽位
    intent: str
    slots: Dict
    missing_slots: List[str]

    # 【Day 3 新增】业务上下文
    context: Dict[str, Any]         # 订单、物流、商品、客户等聚合信息
    context_errors: List[str]       # 上下文收集失败记录

    # 【Day 3 新增】规则匹配
    rule_matches: List[Dict]        # 命中的规则（转 dict 存储，避免序列化问题）
    rule_message: str               # 规则给出的提示语
    rule_next_action: Optional[str] # 规则建议的下一步动作

    # RAG
    query_rewritten: str
    retrieved: List[Dict]
    answer: str
    citations: List[Dict]
    confidence: float

    # 工具调用
    tool_name: Optional[str]
    tool_result: Optional[Dict]

    # 【Day 3 新增】动作执行
    action: Optional[str]
    action_result: Optional[Dict]

    # HITL
    hitl_pending: bool
    hitl_reason: str
    hitl_decision: Optional[str]

    # 状态
    flow_status: str
    error: Optional[str]
