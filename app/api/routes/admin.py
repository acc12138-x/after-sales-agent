"""后台管理 API：读取/更新配置、热重载引擎。"""
from __future__ import annotations

import os
import re
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
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_EMBEDDING_MODEL",
    "CHUNK_SIZE", "CHUNK_OVERLAP",
    "TOP_K_RETRIEVE", "TOP_K_RERANK",
}

SECRET_KEYS = {"DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"}


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
        from app.workflows.nodes import generate
        generate._LLM_LOCAL = None
        generate._LLM_CLOUD = None
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


@router.get("/providers")
async def list_providers():
    """返回可选的 provider 与推荐模型列表。"""
    return {
        "llm_providers": [
            {"value": "ollama", "label": "本地 Ollama"},
            {"value": "deepseek", "label": "云端 DeepSeek"},
        ],
        "embedding_providers": [
            {"value": "ollama", "label": "本地 bge-m3（1024维）"},
            {"value": "dashscope", "label": "云端 DashScope（1024维）"},
        ],
        "ollama_models_available": [
            "qwen2.5-1.5b:latest",
            "modelscope.cn/Qwen/Qwen3-4B-GGUF:latest",
            "qwen-tsx:latest",
        ],
        "ollama_embedding_available": [
            "bge-m3:latest",
            "nomic-embed-text:latest",
        ],
        "deepseek_models": ["deepseek-chat", "deepseek-reasoner"],
        "dashscope_models": ["text-embedding-v3", "text-embedding-v2"],
    }
