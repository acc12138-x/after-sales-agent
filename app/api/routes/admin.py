"""后台管理 API：读取/更新配置、热重载引擎。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])

ENV_PATH = Path(__file__).parents[3] / ".env"

# 允许通过 API 改的键
EDITABLE_KEYS = {
    "LLM_PROVIDER", "EMBEDDING_PROVIDER",
    "OLLAMA_BASE_URL", "OLLAMA_LLM_MODEL", "OLLAMA_EMBEDDING_MODEL",
    "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
    "EMBEDDING_BASE_URL", "EMBEDDING_MODEL", "EMBEDDING_API_KEY",
    "CHROMA_MODE", "CHROMA_HOST", "CHROMA_PORT",
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_EMBEDDING_MODEL",
    "CHUNK_SIZE", "CHUNK_OVERLAP", "MIN_RELEVANCE_SCORE",
    "OPENCLAW_ENABLED", "OPENCLAW_GATEWAY_URL", "OPENCLAW_API_KEY",
    "OPENCLAW_FEISHU_APP_ID", "OPENCLAW_FEISHU_APP_SECRET",
    "TOP_K_RETRIEVE", "TOP_K_RERANK",
}

SECRET_KEYS = {"DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "LLM_API_KEY", "EMBEDDING_API_KEY"}


class ConfigUpdate(BaseModel):
    values: Dict[str, Any]


def _read_env() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _write_env(updates: Dict[str, str]) -> None:
    """把 updates 写回 .env，保留注释和顺序。"""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    keys_done = set()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                keys_done.add(k)
                continue
        new_lines.append(line)

    # 没写过的 key 追加到末尾
    remaining = {k: v for k, v in updates.items() if k not in keys_done}
    if remaining:
        new_lines.append("")
        new_lines.append("# === Auto-updated via admin panel ===")
        for k, v in remaining.items():
            new_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8", newline="\n")


def _mask(v: str) -> str:
    if not v:
        return ""
    return v[:6] + "***" + v[-4:] if len(v) > 12 else "***"


@router.get("/config")
async def get_config():
    env = _read_env()
    result = {}
    for k in EDITABLE_KEYS:
        v = env.get(k, "")
        result[k] = _mask(v) if k in SECRET_KEYS else v
    return {"config": result, "env_path": str(ENV_PATH)}


@router.post("/config")
async def update_config(payload: ConfigUpdate):
    updates = {}
    for k, v in (payload.values or {}).items():
        if k not in EDITABLE_KEYS:
            continue
        v = str(v) if v is not None else ""
        # 脱敏值（如 "sk-xxx***yyy"）跳过，不覆盖
        if k in SECRET_KEYS and "***" in v:
            continue
        updates[k] = v

    if not updates:
        return {"status": "no_change"}

    _write_env(updates)
    return {"status": "ok", "updated_keys": list(updates.keys())}


@router.post("/reload")
async def reload_all():
    """热重载：清掉 settings / embeddings / LLM / rules / intents 缓存。"""
    reloaded = []

    # settings
    try:
        from app.config.settings import get_settings
        get_settings.cache_clear()
        reloaded.append("settings")
    except Exception as e:
        reloaded.append(f"settings_err: {e}")

    # embeddings
    try:
        from app.rag.embedding import get_embeddings
        get_embeddings.cache_clear()
        reloaded.append("embeddings")
    except Exception as e:
        reloaded.append(f"embeddings_err: {e}")

    # LLM 缓存
    try:
        from app.workflows.nodes.generate import reset_llm_cache
        reset_llm_cache()
        reloaded.append("llm")
    except Exception as e:
        reloaded.append(f"llm_err: {e}")

    # retriever（Chroma 客户端需要重建，因为它绑定了 embedding）
    try:
        from app.workflows.nodes.rag_search import reset_retriever
        reset_retriever()
        reloaded.append("retriever")
    except Exception as e:
        reloaded.append(f"retriever_err: {e}")

    # rules
    try:
        from app.rules.factory import reload_engine
        e = reload_engine("after_sales")
        reloaded.append(f"rules({e.size})")
    except Exception as exc:
        reloaded.append(f"rules_err: {exc}")

    # intents
    try:
        from app.intent.factory import reload_intent_engine
        e = reload_intent_engine("default")
        reloaded.append(f"intents({e.size})")
    except Exception as exc:
        reloaded.append(f"intents_err: {exc}")

    # db
    try:
        from app.db.session import reset_engine
        reset_engine()
        reloaded.append("db")
    except Exception as exc:
        reloaded.append(f"db_err: {exc}")

    return {"status": "reloaded", "components": reloaded}


@router.get("/provider-templates")
async def provider_templates():
    """从 YAML 加载 provider 模板。"""
    import yaml
    from pathlib import Path
    template_path = Path(__file__).parents[2] / "config" / "provider_templates.yaml"
    if not template_path.exists():
        return {"llm_providers": {}, "embedding_providers": {}}
    with open(template_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


@router.get("/providers")
async def list_providers():
    """兼容旧接口。"""
    return await provider_templates()


# ============================================================
# Dashboard 聚合数据
# ============================================================
@router.get("/dashboard/stats")
async def dashboard_stats():
    """运营仪表盘聚合数据。"""
    from datetime import datetime, timedelta
    from sqlalchemy import func, select
    from app.db.models.ticket import Ticket
    from app.db.models.user import User
    from app.db.models.audit_log import AuditLog
    from app.db.models.notification import Notification
    from app.db.session import session_scope

    result = {}

    with session_scope() as s:
        # 1. 工单总览
        total = s.execute(select(func.count(Ticket.ticket_id))).scalar() or 0

        status_rows = s.execute(
            select(Ticket.status, func.count(Ticket.ticket_id)).group_by(Ticket.status)
        ).all()
        status_dist = {r[0]: r[1] for r in status_rows}

        # 2. 近 7 天新增
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        days = []
        for i in range(6, -1, -1):
            d_start = today - timedelta(days=i)
            d_end = d_start + timedelta(days=1)
            cnt = s.execute(
                select(func.count(Ticket.ticket_id))
                .where(Ticket.created_at >= d_start)
                .where(Ticket.created_at < d_end)
            ).scalar() or 0
            days.append({"date": d_start.strftime("%m-%d"), "count": cnt})

        # 3. 工程师负载
        eng_rows = s.execute(
            select(User.name, User.current_load, User.max_load, User.status).where(User.role == "engineer")
        ).all()
        engineers = [
            {"name": r[0], "load": r[1], "max": r[2], "status": r[3]}
            for r in eng_rows
        ]

        # 4. 审计 + 通知量
        audit_count = s.execute(select(func.count(AuditLog.id))).scalar() or 0
        notif_count = s.execute(select(func.count(Notification.id))).scalar() or 0

        # 5. 平均解决耗时（从 created_at 到 resolved_at）
        resolved_rows = s.execute(
            select(Ticket.created_at, Ticket.resolved_at)
            .where(Ticket.resolved_at.isnot(None))
        ).all()
        durations = []
        for c, r in resolved_rows:
            if c and r:
                durations.append((r - c).total_seconds())
        avg_resolve_sec = sum(durations) / len(durations) if durations else 0

        result = {
            "total_tickets": total,
            "status_distribution": status_dist,
            "recent_7days": days,
            "engineers": engineers,
            "audit_count": audit_count,
            "notification_count": notif_count,
            "avg_resolve_seconds": round(avg_resolve_sec, 1),
        }

    # 6. 知识库
    try:
        from app.workflows.nodes.rag_search import get_retriever
        r = get_retriever()
        result["knowledge_chunks"] = r.count()
    except Exception:
        result["knowledge_chunks"] = 0

    # 7. SLA 汇总
    try:
        from app.services.sla_service import get_sla_summary
        result["sla_summary"] = get_sla_summary()
    except Exception:
        result["sla_summary"] = {}

    # 8. 退款统计
    try:
        from app.db.models.refund import RefundRequest
        with session_scope() as s:
            total_refunds = s.execute(select(func.count(RefundRequest.refund_id))).scalar() or 0
            total_amount = s.execute(select(func.sum(RefundRequest.amount))).scalar() or 0
            pending = s.execute(
                select(func.count(RefundRequest.refund_id))
                .where(RefundRequest.status == "pending_approval")
            ).scalar() or 0
        result["refund_total"] = total_refunds
        result["refund_amount"] = float(total_amount)
        result["refund_pending"] = pending
    except Exception:
        result["refund_total"] = 0
        result["refund_amount"] = 0
        result["refund_pending"] = 0

    return result

@router.get("/openclaw/status")
async def openclaw_status():
    """探测 OpenClaw 网关是否可达（复用统一探活，结果与 /health 一致）。"""
    from app.config.settings import get_settings
    from app.gateway.health import probe

    result = probe()
    result["feishu_app_id"] = get_settings().openclaw_feishu_app_id or "(未配置)"
    return result


@router.get("/skills")
async def list_skills():
    """列出 OpenClaw Skill 的 JSON Schema（供网关侧注册/发现工具）。"""
    from app.gateway.skills import list_skill_schemas

    items = list_skill_schemas()
    return {"total": len(items), "skills": items}
