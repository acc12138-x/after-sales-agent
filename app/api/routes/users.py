"""人员管理 API（User 表）。"""
from __future__ import annotations
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import get_current_user, require_admin, require_permission
from app.db.models.user import (
    ALL_PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS, User,
)
from app.db.session import session_scope

router = APIRouter(prefix="/users", tags=["users"])

# 列表 / 详情：有「查看人员」权限即可（主管、管理员）
_view = require_permission("user.view")
# 编辑资料 / 飞书绑定 / 重建负载：需要「编辑人员」权限
_edit = require_permission("user.edit")


def _count_admins(s) -> int:
    return len(s.execute(select(User).where(User.role == "admin")).scalars().all())


def _next_user_id(s) -> str:
    """生成不重复的 user_id：取现有最大编号 +1。

    原实现用 len(rows)+1，删过人之后会撞号。
    """
    mx = 0
    for v in s.execute(select(User.user_id)).scalars().all():
        if v and v.startswith("U") and v[1:].isdigit():
            mx = max(mx, int(v[1:]))
    return f"U{mx + 1:04d}"


# ============================================================
# Schemas
# ============================================================
class UserCreate(BaseModel):
    name: str
    # 注册新账号必须给初始密码，否则建出来的账号无法登录
    password: str = ""
    role: str = "engineer"
    job: str = ""
    skills: List[str] = []
    region: str = ""
    status: str = "online"
    max_load: int = 10
    phone: str = ""
    email: str = ""
    feishu_open_id: str = ""
    feishu_chat_id: str = ""
    dept: str = ""
    permissions: dict = {}


class ResetPasswordRequest(BaseModel):
    new_password: str = ""


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    job: Optional[str] = None
    skills: Optional[List[str]] = None
    region: Optional[str] = None
    status: Optional[str] = None
    max_load: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    feishu_open_id: Optional[str] = None
    feishu_chat_id: Optional[str] = None
    dept: Optional[str] = None
    permissions: Optional[dict] = None


class PermissionCheck(BaseModel):
    perm: str


# ============================================================
# 元数据
# ============================================================
@router.get("/meta")
async def get_meta(user: dict = Depends(get_current_user)):
    """返回角色、权限字典，供前端下拉。"""
    return {
        "roles": [
            {"code": k, "label": v} for k, v in ROLE_LABELS.items()
        ],
        "role_permissions": ROLE_PERMISSIONS,
        "all_permissions": ALL_PERMISSIONS,
    }


# ============================================================
# 待绑定飞书账号
# ============================================================
class PendingBindRequest(BaseModel):
    open_id: str
    user_id: int
    chat_id: str = ""


class PendingRecordRequest(BaseModel):
    open_id: str
    chat_id: str = ""
    note: str = ""


@router.get("/pending-bindings")
async def list_pending_bindings(user: dict = Depends(_edit)):
    """列出收到过消息、但还没绑定到人员的飞书 open_id。"""
    from app.services.binding_service import list_pending
    items = list_pending()
    return {"total": len(items), "items": items}


@router.post("/pending-bindings/bind")
async def bind_pending_binding(req: PendingBindRequest, user: dict = Depends(_edit)):
    """把某个 open_id 绑定到指定人员。"""
    from app.services.binding_service import bind
    try:
        return bind(req.open_id, req.user_id, req.chat_id or None)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pending-bindings/record")
async def record_pending_binding(req: PendingRecordRequest, user: dict = Depends(_edit)):
    """手动把一个 open_id 登记进待绑定列表。

    入站链路（OpenClaw / 飞书事件回调）打通后会自动登记；
    未打通时可先手工录入，绑定好再上线。
    """
    from app.services.binding_service import find_user_by_open_id, record_unbound
    if find_user_by_open_id(req.open_id):
        return {"recorded": False, "reason": "该 open_id 已绑定到人员"}
    ok = record_unbound(req.open_id, req.chat_id, req.note)
    return {"recorded": ok}


@router.delete("/pending-bindings/{open_id}")
async def dismiss_pending_binding(open_id: str, user: dict = Depends(_edit)):
    """忽略（删除）一条待绑定记录。"""
    from app.services.binding_service import dismiss
    if not dismiss(open_id):
        raise HTTPException(status_code=404, detail="待绑定记录不存在")
    return {"dismissed": open_id}


# ============================================================
# 列表
# ============================================================
@router.get("")
async def list_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(_view),
):
    with session_scope() as s:
        q = select(User).order_by(User.role, User.current_load, User.id)
        if role:
            q = q.where(User.role == role)
        if status:
            q = q.where(User.status == status)
        rows = s.execute(q).scalars().all()
        return {
            "total": len(rows),
            "items": [u.to_dict() for u in rows],
        }


@router.get("/{user_id}")
async def get_user(user_id: int, user: dict = Depends(_view)):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        return u.to_dict(include_effective=True)


# ============================================================
# 创建（注册新账号）—— 仅管理员
# ============================================================
@router.post("")
async def create_user(req: UserCreate, admin: dict = Depends(require_admin)):
    """注册新账号。**仅管理员可调用。**

    必须给初始密码，否则建出来的账号无法登录。
    """
    from app.services.auth_service import hash_password

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    pwd = (req.password or "").strip()
    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="初始密码至少 6 位")
    if req.role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail=f"未知角色：{req.role}")

    with session_scope() as s:
        exists = s.execute(
            select(User).where(User.name == name)
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail=f"人员 {name} 已存在")

        u = User(
            user_id=_next_user_id(s),
            name=name,
            role=req.role,
            job=req.job,
            skills=json.dumps(req.skills, ensure_ascii=False),
            region=req.region,
            status=req.status,
            max_load=req.max_load,
            current_load=0,
            phone=req.phone,
            email=req.email,
            feishu_open_id=req.feishu_open_id,
            feishu_chat_id=req.feishu_chat_id,
            dept=req.dept,
            permissions=json.dumps(req.permissions or {}, ensure_ascii=False),
            password_hash=hash_password(pwd),
        )
        s.add(u)
        s.flush()
        return u.to_dict(include_effective=True)


# ============================================================
# 更新
# ============================================================
@router.put("/{user_id}")
async def update_user(user_id: int, req: UserUpdate,
                      me: dict = Depends(_edit)):
    """编辑人员资料。

    ⚠️ 角色与权限覆盖**仅管理员**可改 —— 否则有 `user.edit` 的主管
    可以把自己改成 admin，属于越权提权。
    """
    is_admin = me.get("role") == "admin"
    if (req.role is not None or req.permissions is not None) and not is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改角色或权限")

    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")

        if req.name is not None and req.name != u.name:
            dup = s.execute(
                select(User).where(User.name == req.name)
            ).scalar_one_or_none()
            if dup:
                raise HTTPException(status_code=409, detail=f"用户名 {req.name} 已被占用")
            u.name = req.name

        if req.role is not None and req.role != u.role:
            if req.role not in ROLE_LABELS:
                raise HTTPException(status_code=400, detail=f"未知角色：{req.role}")
            # 不允许把最后一名管理员降级，否则系统再没人能管账号
            if u.role == "admin" and _count_admins(s) <= 1:
                raise HTTPException(status_code=400, detail="系统至少需要保留一名管理员")
            u.role = req.role

        if req.job is not None:
            u.job = req.job
        if req.skills is not None:
            u.skills = json.dumps(req.skills, ensure_ascii=False)
        if req.region is not None:
            u.region = req.region
        if req.status is not None:
            u.status = req.status
        if req.max_load is not None:
            u.max_load = req.max_load
        if req.phone is not None:
            u.phone = req.phone
        if req.email is not None:
            u.email = req.email
        if req.feishu_open_id is not None:
            u.feishu_open_id = req.feishu_open_id
        if req.feishu_chat_id is not None:
            u.feishu_chat_id = req.feishu_chat_id
        if req.dept is not None:
            u.dept = req.dept
        if req.permissions is not None:
            u.permissions = json.dumps(req.permissions or {}, ensure_ascii=False)

        s.flush()
        return u.to_dict(include_effective=True)


# ============================================================
# 删除 —— 仅管理员
# ============================================================
@router.delete("/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """删除账号。**仅管理员可调用。**"""
    if user_id == admin.get("id"):
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        if (u.current_load or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该人员还有 {u.current_load or 0} 个进行中工单，无法删除",
            )
        if u.role == "admin":
            raise HTTPException(status_code=400, detail="不能删除管理员账号")
        name = u.name
        s.delete(u)
    return {"deleted": user_id, "name": name}


# ============================================================
# 重置他人密码 —— 仅管理员
# ============================================================
@router.post("/{user_id}/reset-password")
async def reset_password(user_id: int, req: ResetPasswordRequest,
                         admin: dict = Depends(require_admin)):
    """管理员重置某个账号的密码。该账号现有登录状态会立即失效。"""
    from app.services.auth_service import hash_password

    pwd = (req.new_password or "").strip()
    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")

    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        u.password_hash = hash_password(pwd)
        name = u.name

    return {"status": "ok", "user_id": user_id, "name": name,
            "message": f"已重置「{name}」的密码，其现有登录状态已失效"}


# ============================================================
# 状态切换
# ============================================================
@router.post("/{user_id}/toggle-status")
async def toggle_status(user_id: int, user: dict = Depends(_edit)):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        u.status = "offline" if u.status == "online" else "online"
        s.flush()
        return {"id": u.id, "status": u.status}


# ============================================================
# 权限查询
# ============================================================
@router.get("/{user_id}/permissions")
async def get_user_permissions(user_id: int, user: dict = Depends(_view)):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        return {
            "user_id": u.id,
            "name": u.name,
            "role": u.role,
            "effective": sorted(u.effective_permissions()),
            "overrides": u.permission_overrides,
        }


@router.post("/{user_id}/check")
async def check_permission(user_id: int, req: PermissionCheck,
                           user: dict = Depends(_view)):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        return {
            "user_id": u.id,
            "perm": req.perm,
            "allowed": u.has_permission(req.perm),
        }


# ============================================================
# 飞书 open_id 反查
# ============================================================
class ResolveOpenIdRequest(BaseModel):
    mobile: str = ""
    email: str = ""


@router.post("/{user_id}/resolve-open-id")
async def resolve_open_id(user_id: int, req: ResolveOpenIdRequest,
                          user: dict = Depends(_edit)):
    """用手机号 / 邮箱反查【本应用】的 open_id 并写入该人员。

    飞书 open_id 按应用隔离：必须是「发消息那个应用」查出来的才有效，
    否则发送时会报 `99992361 open_id cross app`。
    """
    from app.integrations.feishu_client import batch_get_user_ids

    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        mobile = (req.mobile or u.phone or "").strip()
        email = (req.email or u.email or "").strip()

    if not mobile and not email:
        raise HTTPException(
            status_code=400,
            detail="该人员没有手机号/邮箱，请先在表单里补充（或直接手填 open_id）",
        )

    res = batch_get_user_ids(
        mobiles=[mobile] if mobile else None,
        emails=[email] if email else None,
    )
    if res.get("error"):
        raise HTTPException(status_code=502,
                            detail=f"飞书接口调用失败：{res['error']}")

    found = res.get("open_ids") or {}
    oid = found.get(mobile) or found.get(email) or ""
    if not oid:
        raise HTTPException(
            status_code=404,
            detail=(
                "未查到 open_id。常见原因：该手机号/邮箱对应的用户在飞书里不存在，"
                "或不在本应用的「可用范围」内。"
                "请到飞书开放平台把该用户加入应用可用范围后重试。"
            ),
        )

    with session_scope() as s:
        u = s.get(User, user_id)
        u.feishu_open_id = oid
        name = u.name

    return {"user_id": user_id, "name": name, "feishu_open_id": oid}


# ============================================================
# 重建负载
# ============================================================
@router.post("/rebuild-load")
async def rebuild_load(user: dict = Depends(_edit)):
    """从 tickets 表重建每个人员的当前负载。"""
    from sqlalchemy import func
    from app.db.models.ticket import Ticket

    with session_scope() as s:
        rows = s.execute(
            select(Ticket.assigned_to, func.count(Ticket.ticket_id))
            .where(Ticket.status.in_(["assigned", "accepted", "in_progress"]))
            .group_by(Ticket.assigned_to)
        ).all()
        active_counts = {r[0]: r[1] for r in rows if r[0]}

        users = s.execute(select(User)).scalars().all()
        updated = []
        for u in users:
            new_load = active_counts.get(u.name, 0)
            old = u.current_load
            u.current_load = new_load
            updated.append({"name": u.name, "old": old, "new": new_load})

        return {"updated": updated, "active_tickets": sum(active_counts.values())}
