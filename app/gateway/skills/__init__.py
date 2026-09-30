"""OpenClaw Skill 注册表。

OpenClaw 侧以 **Skill** 的形式调用后端能力。这里把 5 个 Skill 集中注册：

- 统一导出 JSON Schema，供 `GET /admin/skills` 被发现（网关侧据此注册工具）
- 提供本地直调入口 `invoke_skill()`，便于自测

说明：Skill 的"正式执行路径"是 OpenClaw 网关按 schema 调用；
`invoke_skill()` 主要用于本地自测与后端内部复用。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from app.gateway.skills.assign_ticket import SCHEMA as _S_ASSIGN
from app.gateway.skills.assign_ticket import assign_ticket
from app.gateway.skills.create_ticket import SCHEMA as _S_CREATE
from app.gateway.skills.create_ticket import create_ticket
from app.gateway.skills.notify_human import SCHEMA as _S_NOTIFY
from app.gateway.skills.notify_human import notify_human
from app.gateway.skills.query_order import SCHEMA as _S_ORDER
from app.gateway.skills.query_order import query_order
from app.gateway.skills.search_kb import SCHEMA as _S_KB
from app.gateway.skills.search_kb import search_kb

_HANDLERS: Dict[str, Callable[..., Any]] = {
    "search_kb": search_kb,
    "query_order": query_order,
    "create_ticket": create_ticket,
    "assign_ticket": assign_ticket,
    "notify_human": notify_human,
}

_SCHEMAS: List[Dict[str, Any]] = [
    _S_KB, _S_ORDER, _S_CREATE, _S_ASSIGN, _S_NOTIFY,
]

__all__ = [
    "search_kb", "query_order", "create_ticket", "assign_ticket", "notify_human",
    "list_skill_schemas", "list_skill_names", "get_skill", "invoke_skill",
]


def list_skill_schemas() -> List[Dict[str, Any]]:
    """全部 Skill 的 JSON Schema（返回副本，避免调用方改到源对象）。"""
    return [dict(s) for s in _SCHEMAS]


def list_skill_names() -> List[str]:
    return list(_HANDLERS.keys())


def get_skill(name: str) -> Callable[..., Any] | None:
    return _HANDLERS.get(name)


def invoke_skill(name: str, **kwargs: Any) -> Any:
    """本地直调某个 Skill（自测用）。"""
    fn = _HANDLERS.get(name)
    if fn is None:
        raise KeyError(f"未注册的 Skill: {name}（可用：{list(_HANDLERS)}）")
    return fn(**kwargs)
