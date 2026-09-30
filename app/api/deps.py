"""FastAPI 公共依赖：当前用户解析 + 权限 / 管理员校验。

把 `get_current_user` 从 `routes/auth.py` 提到这里，避免路由模块之间互import；
各业务路由统一从这里取依赖。
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException

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
