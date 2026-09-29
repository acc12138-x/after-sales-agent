from __future__ import annotations
import uuid
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter
from langgraph.types import Command

from app.api.schemas.models import ChatRequest, ChatResponse
from app.workflows.graph import graph
from app.config.settings import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])


APPROVE_WORDS = ["同意", "确认", "批准", "通过", "可以", "好的", "好", "approve", "yes", "ok", "okay"]
REJECT_WORDS = ["拒绝", "驳回", "不同意", "不行", "取消", "否", "reject", "no"]


def _parse_decision(text: str):
    t = (text or "").strip().lower()
    if not t:
        return None
    for w in REJECT_WORDS:
        if t == w.lower() or t.startswith(w.lower()):
            return "block_revise: 用户拒绝"
    for w in APPROVE_WORDS:
        if t == w.lower() or t.startswith(w.lower()):
            return "approve"
    return None


def _hitl_age_seconds(snapshot) -> float:
    try:
        created_at = getattr(snapshot, "created_at", None)
        if not created_at:
            return 0.0
        if isinstance(created_at, str):
            s = created_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
        else:
            dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return 0.0


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    trace_id = uuid.uuid4().hex
    print(f"\n[CHAT] trace_id={trace_id[:8]} thread={req.thread_id} msg={req.message[:60]!r}")
    config = {"configurable": {"thread_id": req.thread_id}}
    settings = get_settings()
    timeout_sec = getattr(settings, "hitl_timeout_seconds", 1800)

    is_interrupted = False
    try:
        snapshot = graph.get_state(config)
        is_interrupted = bool(snapshot and snapshot.next)
    except Exception:
        snapshot = None
        is_interrupted = False

    try:
        if is_interrupted:
            age = _hitl_age_seconds(snapshot)

            # 超时自动取消
            if age > timeout_sec:
                final = graph.invoke(Command(resume="block_revise: timeout"), config=config)
                return ChatResponse(
                    thread_id=req.thread_id,
                    answer="【超时】操作已自动取消，请重新发起。",
                    intent=final.get("intent"),
                    confidence=0.0,
                    citations=[],
                    flow_status="cancelled",
                    hitl_pending=False,
                    hitl_reason=None,
                )

            decision = _parse_decision(req.message)
            if decision is None:
                return ChatResponse(
                    thread_id=req.thread_id,
                    answer=f"当前有待确认的操作（已等待 {int(age)} 秒），请回复「同意」或「拒绝」。",
                    intent=None,
                    confidence=0.0,
                    citations=[],
                    flow_status="waiting",
                    hitl_pending=True,
                    hitl_reason="等待用户确认",
                )
            final = graph.invoke(Command(resume=decision), config=config)
        else:
            init = {
                "thread_id": req.thread_id,
                "trace_id": trace_id,
                "user_input": req.message,
                "messages": [],
                "slots": {},
            }
            final = graph.invoke(init, config=config)
    except Exception as e:
        tb = traceback.format_exc()
        print("=" * 60)
        print("[CHAT ERROR]", e)
        print(tb)
        print("=" * 60)
        return ChatResponse(
            thread_id=req.thread_id,
            answer=f"处理失败：{type(e).__name__}: {e}",
            intent=None,
            confidence=0.0,
            citations=[],
            flow_status="error",
            hitl_pending=False,
            hitl_reason=None,
        )

    answer = (final.get("answer") or "").strip()

    if final.get("hitl_pending"):
        reason = final.get("hitl_reason") or "需要人工确认"
        prefix = f"【需要人工确认】{reason}"
        if answer and not answer.startswith("【需要人工确认】"):
            answer = prefix + "\n\n" + answer
        elif not answer:
            answer = prefix + "\n\n请回复「同意」或您的具体意见。"

    if not answer:
        status = final.get("flow_status", "")
        if status == "waiting":
            missing = final.get("missing_slots") or []
            answer = "请补充：" + "、".join(missing) if missing else "等待人工处理中..."
        elif final.get("intent") == "ticket":
            answer = "工单创建中，请稍候..."
        else:
            answer = "暂无相关依据，建议转人工。"

    intent = final.get("intent")
    raw_conf = final.get("confidence")
    if intent in ("ticket", "order_query", "logistics"):
        confidence = 0.0
    else:
        confidence = float(raw_conf or 0.0)

    return ChatResponse(
        thread_id=req.thread_id,
        answer=answer,
        intent=intent,
        confidence=confidence,
        citations=final.get("citations", []) or [],
        flow_status=final.get("flow_status", "succeeded"),
        hitl_pending=bool(final.get("hitl_pending", False)),
        hitl_reason=final.get("hitl_reason"),
    )
