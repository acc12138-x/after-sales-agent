
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from app.workflows.graph import graph

router = APIRouter(prefix="/threads", tags=["stream"])


def safe_json(obj: Any) -> str:
    """把任意对象转成 JSON 字符串，遇到不可序列化的对象做降级处理。"""
    def _default(o):
        # Interrupt 对象
        if hasattr(o, "value"):
            return {"__interrupt__": True, "value": _to_serializable(o.value)}
        if hasattr(o, "to_json"):
            try:
                return o.to_json()
            except Exception:
                pass
        return str(o)

    return json.dumps(obj, ensure_ascii=False, default=_default)


def _to_serializable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(x) for x in obj]
    return str(obj)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {safe_json(data)}\n\n"


def classify_event(node_name: str, node_output: Any) -> tuple[str, dict]:
    """把 LangGraph 输出映射到 Bridge 契约的 5 种事件类型。"""

    # 1) 中断事件：LangGraph 用 __interrupt__ 作为 key
    if node_name == "__interrupt__":
        # node_output 可能是 tuple / list / 单个 Interrupt
        items = node_output if isinstance(node_output, (list, tuple)) else [node_output]
        first = items[0] if items else {}
        payload = getattr(first, "value", first)
        return "hitl", {"type": "hitl", "payload": _to_serializable(payload)}

    # 2) 节点执行结果
    if isinstance(node_output, dict):
        status = node_output.get("flow_status")
        if status in ("succeeded", "rejected", "waiting"):
            return "milestone", {
                "type": "milestone",
                "node": node_name,
                "status": status,
            }

    # 3) 其他一律作为 status（静默）
    return "status", {"type": "status", "node": node_name}


def build_fallback_answer(state: dict) -> str:
    """HITL 场景下没有 RAG answer，根据 intent 给一个提示语。"""
    intent = state.get("intent", "")
    if intent == "human":
        return "已转人工，客服稍后接入。"
    if intent == "complaint":
        return "已记录您的反馈，正在转交人工处理。"
    return state.get("answer", "") or ""


@router.post("/{thread_id}/runs/stream")
async def stream_run(thread_id: str, request: Request):
    body = await request.json()
    user_input = body.get("input", {})
    message = user_input.get("message", "")
    messages = user_input.get("messages", [])

    init = {
        "thread_id": thread_id,
        "user_input": message,
        "messages": messages,
        "slots": {},
    }
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator() -> AsyncGenerator[str, None]:
        yield sse("status", {"type": "status", "message": "开始处理"})

        try:
            async for chunk in graph.astream(init, config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    event_type, payload = classify_event(node_name, node_output)
                    yield sse(event_type, payload)

            snapshot = graph.get_state(config)
            final_values = snapshot.values if snapshot else {}

            # 中断中：停在 hitl_gate，等待 resume
            if snapshot and snapshot.next:
                yield sse("hitl", {
                    "type": "hitl",
                    "thread_id": thread_id,
                    "reason": final_values.get("hitl_reason") or "需要人工确认",
                    "intent": final_values.get("intent"),
                })
                return

            # 正常结束
            answer = final_values.get("answer", "") or build_fallback_answer(final_values)
            yield sse("terminal", {
                "type": "terminal",
                "status": final_values.get("flow_status", "succeeded"),
                "answer": answer,
                "confidence": final_values.get("confidence", 0.0),
                "citations": final_values.get("citations", []),
                "intent": final_values.get("intent"),
            })

        except Exception as e:
            yield sse("terminal", {
                "type": "terminal",
                "status": "failed",
                "error": str(e),
            })

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{thread_id}/runs/resume")
async def resume_run(thread_id: str, request: Request):
    body = await request.json()
    decision = body.get("decision", "approve")
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(Command(resume=decision), config=config)
        answer = result.get("answer", "") or build_fallback_answer(result)
        return {
            "thread_id": thread_id,
            "decision": decision,
            "flow_status": result.get("flow_status", "succeeded"),
            "answer": answer,
            "intent": result.get("intent"),
        }
    except Exception as e:
        return {"thread_id": thread_id, "status": "failed", "error": str(e)}


@router.get("/{thread_id}/state")
async def get_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot:
        return {"thread_id": thread_id, "exists": False}
    return {
        "thread_id": thread_id,
        "exists": True,
        "next": list(snapshot.next) if snapshot.next else [],
        "values": {
            "intent": snapshot.values.get("intent"),
            "flow_status": snapshot.values.get("flow_status"),
            "hitl_pending": snapshot.values.get("hitl_pending"),
            "answer": (snapshot.values.get("answer") or "")[:200],
        },
    }
