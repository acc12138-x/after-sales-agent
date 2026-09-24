
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
    final = graph.invoke(init)

    return ChatResponse(
        thread_id=req.thread_id,
        answer=final.get("answer") or "",
        intent=final.get("intent"),
        confidence=float(final.get("confidence", 0.0)),
        citations=final.get("citations", []) or [],
        flow_status=final.get("flow_status", "succeeded"),
        hitl_pending=bool(final.get("hitl_pending", False)),
        hitl_reason=final.get("hitl_reason"),
    )
