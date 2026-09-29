"""权限校验服务。"""
from __future__ import annotations
from typing import Optional

from sqlalchemy import select

from app.db.models.user import ROLE_LABELS, User
from app.db.session import session_scope


# 飞书命令 action → 需要的权限
FEISHU_ACTION_PERMISSIONS = {
    "accept":          "ticket.accept",
    "start":           "ticket.accept",
    "resolve":         "ticket.resolve",
    "reject":          "ticket.reject",
    "reassign":        "ticket.reassign",
    "approve_refund":  "refund.approve",
    "reject_refund":   "refund.approve",
    "execute_refund":  "refund.execute",
}


def _user_to_dict(u: User) -> dict:
    """在 session 内转 dict，避免 detached ORM 问题。"""
    perms = sorted(u.effective_permissions())
    d = u.to_dict()
    d["effective_permissions"] = perms
    return d


def get_user_by_feishu(open_id: str) -> Optional[dict]:
    """返回 dict（不是 ORM 对象），避免 session 关闭后访问属性失败。"""
    if not open_id:
        return None
    with session_scope() as s:
        u = s.execute(
            select(User).where(User.feishu_open_id == open_id)
        ).scalar_one_or_none()
        if u is None:
            return None
        return _user_to_dict(u)


def get_user_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    with session_scope() as s:
        u = s.execute(select(User).where(User.name == name)).scalar_one_or_none()
        if u is None:
            return None
        return _user_to_dict(u)


def _has_perm(perms: list, required: str) -> bool:
    if not required:
        return True
    if "*" in perms or required in perms:
        return True
    prefix = required.split(".")[0] + ".*"
    return prefix in perms


def check_feishu_command(open_id: str, action: str) -> dict:
    """
    校验飞书命令权限。
    返回：
      {"allowed": True, "user": {...}}
      {"allowed": False, "reason": "...", "user_name": "..."}
    """
    # 开发模式：没传 open_id 时放行
    if not open_id:
        return {"allowed": True, "user": None, "reason": "no_open_id"}

    user = get_user_by_feishu(open_id)
    if user is None:
        return {
            "allowed": False,
            "reason": f"飞书账号 {open_id[:12]}... 未绑定系统用户",
            "user_name": None,
        }

    required = FEISHU_ACTION_PERMISSIONS.get(action)
    if not required:
        return {"allowed": True, "user": user, "reason": "no_required"}

    perms = user.get("effective_permissions", [])
    if not _has_perm(perms, required):
        return {
            "allowed": False,
            "reason": f"角色「{ROLE_LABELS.get(user.get('role'), user.get('role'))}」无权执行 `{action}`（缺 {required}）",
            "user_name": user.get("name"),
            "required": required,
        }

    return {
        "allowed": True,
        "user": user,
        "reason": "ok",
    }
