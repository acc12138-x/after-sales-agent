
"""OpenAI 兼容层：让 OpenClaw 把 LangGraph 当作一个自定义模型 Provider。

支持:
- POST /v1/chat/completions  (stream / non-stream)
- GET  /v1/models
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.workflows.graph import graph

router = APIRouter(prefix="/v1", tags=["openai-compat"])

_session_map: Dict[str, str] = {}


def _thread_id(session_key: str | None) -> str:
    if not session_key:
        return f"openclaw-{uuid.uuid4().hex[:8]}"
    if session_key not in _session_map:
        _session_map[session_key] = f"openclaw-{session_key[:20]}"
    return _session_map[session_key]


def _extract_user_message(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts.append(c.get("text", ""))
                return " ".join(parts)
    return ""


class ChatCompletionRequest(BaseModel):
    model: str = "local-rag"
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None
    session_id: Optional[str] = None
    sessionId: Optional[str] = None


def _run_graph(user_msg: str, session_key: str | None) -> Dict[str, Any]:
    """调用 LangGraph，返回最终状态。checkpointer 需要 thread_id。"""
    tid = _thread_id(session_key)
    init = {
        "thread_id": tid,
        "user_input": user_msg,
        "messages": [],
        "slots": {},
    }
    config = {"configurable": {"thread_id": tid}}
    final = graph.invoke(init, config=config)
    return final


def _build_answer(final: Dict[str, Any]) -> str:
    if final.get("hitl_pending"):
        reason = final.get("hitl_reason") or "需要人工确认"
        return f"【需要人工确认】{reason}\n\n请回复「同意」或您的具体意见。"

    answer = final.get("answer") or ""
    if not answer:
        intent = final.get("intent", "")
        if intent == "human":
            answer = "已转人工，客服稍后接入。"
        elif final.get("missing_slots"):
            answer = "请补充：" + "、".join(final["missing_slots"])
        else:
            answer = "暂无相关依据，建议转人工。"

    citations = final.get("citations") or []
    if citations and final.get("confidence", 0) > 0.5:
        sources = []
        for c in citations[:3]:
            src = c.get("source") or c.get("chunk_id", "")[:8]
            sources.append(f"[{c['index']}] {src}")
        answer = answer + "\n\n参考来源：\n" + "\n".join(sources)

    return answer


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request):
    user_msg = _extract_user_message(req.messages)
    session_key = req.session_id or req.sessionId or req.user

    final = _run_graph(user_msg, session_key)
    answer = _build_answer(final)

    created = int(time.time())
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    if not req.stream:
        return {
            "id": resp_id,
            "object": "chat.completion",
            "created": created,
            "model": req.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    async def stream_gen() -> AsyncGenerator[str, None]:
        chunk0 = {
            "id": resp_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": req.model,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }],
        }
        yield f"data: {json.dumps(chunk0, ensure_ascii=False)}\n\n"

        step = 20
        for i in range(0, len(answer), step):
            piece = answer[i:i + step]
            chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": piece},
                    "finish_reason": None,
                }],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        end_chunk = {
            "id": resp_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": req.model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }],
        }
        yield f"data: {json.dumps(end_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_gen(), media_type="text/event-stream")


@router.get("/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "local-rag",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-rag",
            },
            {
                "id": "local-rag-search",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-rag",
            },
        ],
    }
