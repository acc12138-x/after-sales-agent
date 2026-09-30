"""认证 API：登录 / 查自己 / 改密码。"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.auth_service import (
    authenticate, create_token, decode_token, get_user_by_id, hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    name: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ============================================================
# 依赖：从 Header 取当前用户
# ============================================================
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """从 Authorization: Bearer xxx 里解析用户。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user_id = int(payload.get("sub", 0))
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# ============================================================
# 端点
# ============================================================
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user = authenticate(req.name, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="姓名或密码错误")
    token = create_token(user["id"], user["name"], user["role"])
    return LoginResponse(token=token, user=user)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    # JWT 无状态，前端删 token 即可
    return {"status": "ok", "message": "已登出"}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    from app.db.models.user import User
    from app.db.session import session_scope
    from app.services.auth_service import verify_password

    with session_scope() as s:
        u = s.get(User, user["id"])
        if u is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not verify_password(req.old_password, u.password_hash or ""):
            raise HTTPException(status_code=400, detail="原密码错误")
        if len(req.new_password) < 6:
            raise HTTPException(status_code=400, detail="新密码至少 6 位")
        u.password_hash = hash_password(req.new_password)
    return {"status": "ok", "message": "密码已修改"}
