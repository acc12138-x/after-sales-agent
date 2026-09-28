
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


def _run_graph(user_msg: str, session_key: str | None, messages: list = None) -> Dict[str, Any]:
    """调用 LangGraph，返回最终状态。checkpointer 需要 thread_id。"""
    tid = _thread_id(session_key)
    # 传历史消息（供多轮上下文检测）
    history = []
    for m in (messages or []):
        role = m.get("role")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": str(content)})

    init = {
        "thread_id": tid,
        "user_input": user_msg,
        "messages": history,
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

    # ============ 飞书命令识别 ============
    cmd = _extract_command(user_msg)
    if cmd:
        cmd_result = _handle_feishu_command(cmd)
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
                    "message": {"role": "assistant", "content": cmd_result},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        # 流式返回
        async def cmd_stream():
            chunk = {
                "id": resp_id, "object": "chat.completion.chunk",
                "created": created, "model": req.model,
                "choices": [{"index": 0, "delta": {"content": cmd_result}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            end = {
                "id": resp_id, "object": "chat.completion.chunk",
                "created": created, "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(end, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(cmd_stream(), media_type="text/event-stream")

    final = _run_graph(user_msg, session_key, req.messages)
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

# ============================================================
# 飞书命令识别（张工在飞书回复"完成 Txxx"触发状态更新）
# ============================================================
import re as _re_cmd

TICKET_ID_PAT = r"(T[A-Z0-9]{8})"

# 命令模式（两种顺序都支持）
CMD_PATTERNS = [
    ("resolve", _re_cmd.compile(rf"(完成|修好|处理完|搞定|已修复|已完成|已处理|处理好|处理了|处理掉).{{0,8}}{TICKET_ID_PAT}", _re_cmd.IGNORECASE)),
    ("resolve", _re_cmd.compile(rf"{TICKET_ID_PAT}.{{0,8}}(已完成|修好|处理完|搞定|已修复|已处理|处理好|处理了|处理掉)", _re_cmd.IGNORECASE)),
    ("accept", _re_cmd.compile(rf"(接单|我接了|我接受|接受工单).{{0,8}}{TICKET_ID_PAT}", _re_cmd.IGNORECASE)),
    ("accept", _re_cmd.compile(rf"{TICKET_ID_PAT}.{{0,8}}(接单|我接了|我接受)", _re_cmd.IGNORECASE)),
    ("reject", _re_cmd.compile(rf"(拒单|拒绝|不接|我拒绝).{{0,8}}{TICKET_ID_PAT}", _re_cmd.IGNORECASE)),
    ("start", _re_cmd.compile(rf"(开始处理|开工|已开始|处理|跟进|接手).{{0,8}}{TICKET_ID_PAT}", _re_cmd.IGNORECASE)),
    ("start", _re_cmd.compile(rf"{TICKET_ID_PAT}.{{0,8}}(开始处理|开工|已开始)", _re_cmd.IGNORECASE)),
]

# 状态中文映射
STATUS_CN = {
    "accepted": "已接单",
    "in_progress": "处理中",
    "resolved": "已完成（待主管审批）",
    "closed": "已关闭",
    "assigned": "待接单",
}

# 允许的命令触发状态
ALLOWED_STATUS = {
    "accept": "accepted",
    "start": "in_progress",
    "resolve": "resolved",
    "reject": "rejected",
}


def _extract_command(text: str) -> dict | None:
    """从消息中提取飞书命令。返回 {action, ticket_id, raw} 或 None。"""
    if not text:
        return None

    # 预处理：去掉 @机器人名 后缀
    import re as _re_at
    text = _re_at.sub(r"\s*@[^\s]+.*$", "", text).strip()
    # 兼容 @@ 双 @
    text = _re_at.sub(r"@+.*$", "", text).strip()

    for action, pattern in CMD_PATTERNS:
        m = pattern.search(text)
        if m:
            # 找到工单号（可能在第 2 组或第 1 组）
            tid = None
            for g in m.groups():
                if g and _re_cmd.match(TICKET_ID_PAT + r"$", g, _re_cmd.IGNORECASE):
                    tid = g.upper()
                    break
            if tid:
                return {"action": action, "ticket_id": tid, "raw": text}
    return None


def _handle_feishu_command(cmd: dict) -> str:
    """执行飞书命令，更新工单状态。返回给用户的提示文本。"""
    from app.api.routes import tickets as tk
    from app.db.models.ticket import Ticket
    from app.db.session import session_scope
    from app.audit.logger import log as audit_log
    from app.notify.notifier import send as notify

    action = cmd["action"]
    tid = cmd["ticket_id"]

    # 检查工单存在
    with session_scope() as s:
        t = s.get(Ticket, tid)
        if t is None:
            return f"❌ 未找到工单 {tid}"

        old_status = t.status
        target_status = ALLOWED_STATUS.get(action)

        # 状态校验
        if target_status == "resolved" and old_status not in ("accepted", "in_progress"):
            return f"⚠️ 工单 {tid} 当前状态为 {STATUS_CN.get(old_status, old_status)}，不能标记完成"

        if target_status == "accepted" and old_status != "assigned":
            return f"⚠️ 工单 {tid} 当前状态为 {STATUS_CN.get(old_status, old_status)}，不能接单"

        if target_status == "in_progress" and old_status != "accepted":
            return f"⚠️ 工单 {tid} 当前状态为 {STATUS_CN.get(old_status, old_status)}，不能开始处理"

    # 执行状态流转
    try:
        if action == "accept":
            tk._transition(tid, "accepted")
            msg = f"✅ 工单 {tid} 已接单"
        elif action == "start":
            tk._transition(tid, "in_progress")
            msg = f"🔧 工单 {tid} 已开始处理"
        elif action == "resolve":
            tk._transition(tid, "resolved", extra={"resolved_note": "工程师通过飞书反馈完成"})
            msg = f"🎯 工单 {tid} 已标记完成，**待主管审批**"
        elif action == "reject":
            tk._transition(tid, "rejected", extra={"reject_reason": "工程师通过飞书拒单"})
            msg = f"❌ 工单 {tid} 已拒单，系统将自动重派"
        else:
            msg = f"⚠️ 未知操作 {action}"

        # 通知 + 审计
        audit_log(
            action=f"feishu.{action}",
            actor="feishu",
            target_type="ticket",
            target_id=tid,
            detail={"via": "feishu", "raw": cmd["raw"][:80]},
        )
        return msg
    except Exception as e:
        return f"❌ 操作失败：{e}"
