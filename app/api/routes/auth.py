"""认证 API：登录 / 查自己 / 改密码。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user  # noqa: F401  兼容旧的导入路径
from app.services.auth_service import authenticate, create_token, hash_password

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
# 端点
# ============================================================
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user = authenticate(req.name, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="姓名或密码错误")
    token = create_token(user["id"], user["name"], user["role"], user.get("pv", ""))
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
    """任何已登录账号都可以改自己的密码。

    改完密码后，此前的 token 会因密码指纹不匹配而全部失效（需重新登录）。
    """
    from app.db.models.user import User
    from app.db.session import session_scope
    from app.services.auth_service import verify_password

    new_pwd = (req.new_password or "").strip()
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    if new_pwd == (req.old_password or ""):
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    with session_scope() as s:
        u = s.get(User, user["id"])
        if u is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not verify_password(req.old_password, u.password_hash or ""):
            raise HTTPException(status_code=400, detail="原密码错误")
        u.password_hash = hash_password(new_pwd)

    return {"status": "ok", "message": "密码已修改，请用新密码重新登录"}
