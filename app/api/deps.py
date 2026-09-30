"""FastAPI 公共依赖：当前用户解析 + 权限 / 管理员校验 + 网关鉴权。

把 `get_current_user` 从 `routes/auth.py` 提到这里，避免路由模块之间互import；
各业务路由统一从这里取依赖。

两套鉴权：
  - 管理后台（浏览器）：JWT 会话            -> get_current_user / require_permission / require_admin
  - OpenClaw 网关（服务端到服务端）：API Key -> get_gateway_caller
    网关不是登录用户，套 JWT 会把入站链路打断。
"""
from __future__ import annotations

import secrets
from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException

from app.config.settings import get_settings
from app.services.auth_service import decode_token, get_user_by_id
from app.services.permission import has_perm


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """从 `Authorization: Bearer xxx` 解析当前用户。

    返回的是 dict（含 effective_permissions），不是 ORM 对象。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token 内容非法")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    # 密码指纹比对：改过密码后，旧 token 立即失效
    if payload.get("pv") != user.get("pv"):
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    return user


def require_permission(perm: str) -> Callable[..., dict]:
    """依赖工厂：要求当前用户具备 `perm`（`*` 视为全权）。"""

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        perms = user.get("effective_permissions") or []
        if has_perm(perms, perm):
            return user
        raise HTTPException(status_code=403, detail=f"需要权限：{perm}")

    return _dep


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """仅管理员。用于注册账号、删除账号等敏感操作。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return user


def get_gateway_caller(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict:
    """校验 OpenClaw 网关调用方（`/v1/*`、`/threads/*`）。

    网关是服务端调用，没有登录会话，因此用共享 API Key 而不是 JWT：
    网关侧 Provider 里配的 Key 必须与后端 `OPENCLAW_API_KEY` 一致。

    若 `OPENCLAW_REQUIRE_KEY=false` 或未配置 API Key，则跳过校验
    （便于网关侧还没配好 Key 时先跑通链路）。
    """
    s = get_settings()
    required = (getattr(s, "openclaw_api_key", "") or "").strip()
    if not getattr(s, "openclaw_require_key", True) or not required:
        return {"caller": "gateway", "verified": False}

    got = (x_api_key or "").strip()
    if not got and authorization and authorization.startswith("Bearer "):
        got = authorization[7:].strip()

    if not got or not secrets.compare_digest(got, required):
        raise HTTPException(
            status_code=401,
            detail=(
                "网关鉴权失败：请在 OpenClaw 的 Provider 中把 API Key 配成与后端 "
                "OPENCLAW_API_KEY 一致（若网关侧暂未配置，可临时设置 "
                "OPENCLAW_REQUIRE_KEY=false 关闭校验）"
            ),
        )
    return {"caller": "gateway", "verified": True}
