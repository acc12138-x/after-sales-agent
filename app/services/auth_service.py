"""认证服务：密码 hash + JWT 签发/校验。"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config.settings import get_settings
from app.db.models.user import User
from app.db.session import session_scope


def hash_password(password: str, salt: str = "") -> str:
    """SHA256(salt + password)。salt 为空时生成新 salt。"""
    if not salt:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored_hash: str) -> bool:
    """校验密码。"""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, _, _ = stored_hash.partition("$")
    return hash_password(password, salt) == stored_hash


def create_token(user_id: int, name: str, role: str) -> str:
    """签发 JWT。"""
    s = get_settings()
    expire_hours = int(getattr(s, "jwt_expire_hours", 168))
    payload = {
        "sub": str(user_id),
        "name": name,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """解析 JWT。失败返回 None。"""
    try:
        s = get_settings()
        return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None


def authenticate(name: str, password: str) -> Optional[dict]:
    """姓名 + 密码登录。成功返回 user dict，失败返回 None。"""
    from sqlalchemy import select
    with session_scope() as s:
        u = s.execute(select(User).where(User.name == name)).scalar_one_or_none()
        if u is None:
            return None
        if not u.password_hash:
            return None
        if not verify_password(password, u.password_hash):
            return None

        # 在 session 内转 dict
        d = u.to_dict()
        d["effective_permissions"] = sorted(u.effective_permissions())
        return d


def get_user_by_id(user_id: int) -> Optional[dict]:
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            return None
        d = u.to_dict()
        d["effective_permissions"] = sorted(u.effective_permissions())
        return d


def ensure_admin_password() -> None:
    """如果管理员还没密码，设默认密码 admin123。"""
    from sqlalchemy import select
    with session_scope() as s:
        u = s.execute(select(User).where(User.role == "admin")).scalar_one_or_none()
        if u and not u.password_hash:
            u.password_hash = hash_password("admin123")
            print("[AUTH] 管理员默认密码已设置: admin123")
