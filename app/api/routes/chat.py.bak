
from __future__ import annotations
from fastapi import APIRouter

from app.api.schemas.models import ChatRequest, ChatResponse
from app.workflows.graph import graph

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    init = {
        "thread_id": req.thread_id,
        "user_input": req.message,
        "messages": [],
        "slots": {},
    }
    config = {"configurable": {"thread_id": req.thread_id}}
    final = graph.invoke(init, config=config)

    answer = final.get("answer") or ""

    # 兜底：answer 为空时
    if not answer.strip():
        status = final.get("flow_status", "")
        if status == "waiting":
            missing = final.get("missing_slots") or []
            answer = "请补充：" + "、".join(missing) if missing else "等待人工处理中..."
        elif final.get("intent") == "ticket":
            answer = "工单创建中，请稍候..."
        else:
            answer = "暂无相关依据，建议转人工。"

    return ChatResponse(
        thread_id=req.thread_id,
        answer=answer,
        intent=final.get("intent"),
        confidence=float(final.get("confidence", 0.0) or 0.0),
        citations=final.get("citations", []) or [],
        flow_status=final.get("flow_status", "succeeded"),
        hitl_pending=bool(final.get("hitl_pending", False)),
        hitl_reason=final.get("hitl_reason"),
    )
