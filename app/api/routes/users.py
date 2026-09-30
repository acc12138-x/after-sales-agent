"""人员管理 API（User 表）。"""
from __future__ import annotations
import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models.user import (
    ALL_PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS, User,
)
from app.db.session import session_scope

router = APIRouter(prefix="/users", tags=["users"])


# ============================================================
# Schemas
# ============================================================
class UserCreate(BaseModel):
    name: str
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
async def get_meta():
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
async def list_pending_bindings():
    """列出收到过消息、但还没绑定到人员的飞书 open_id。"""
    from app.services.binding_service import list_pending
    items = list_pending()
    return {"total": len(items), "items": items}


@router.post("/pending-bindings/bind")
async def bind_pending_binding(req: PendingBindRequest):
    """把某个 open_id 绑定到指定人员。"""
    from app.services.binding_service import bind
    try:
        return bind(req.open_id, req.user_id, req.chat_id or None)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pending-bindings/record")
async def record_pending_binding(req: PendingRecordRequest):
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
async def dismiss_pending_binding(open_id: str):
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
async def get_user(user_id: int):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")
        return u.to_dict(include_effective=True)


# ============================================================
# 创建
# ============================================================
@router.post("")
async def create_user(req: UserCreate):
    with session_scope() as s:
        exists = s.execute(
            select(User).where(User.name == req.name)
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail=f"人员 {req.name} 已存在")

        # 生成 user_id
        cnt = s.execute(select(User)).scalars().all()
        uid = f"U{(len(cnt) + 1):04d}"

        u = User(
            user_id=uid,
            name=req.name,
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
        )
        s.add(u)
        s.flush()
        return u.to_dict(include_effective=True)


# ============================================================
# 更新
# ============================================================
@router.put("/{user_id}")
async def update_user(user_id: int, req: UserUpdate):
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="人员不存在")

        if req.name is not None:
            u.name = req.name
        if req.role is not None:
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
# 删除
# ============================================================
@router.delete("/{user_id}")
async def delete_user(user_id: int):
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
            raise HTTPException(status_code=400, detail="不能删除管理员")
        s.delete(u)
    return {"deleted": user_id}


# ============================================================
# 状态切换
# ============================================================
@router.post("/{user_id}/toggle-status")
async def toggle_status(user_id: int):
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
async def get_user_permissions(user_id: int):
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
async def check_permission(user_id: int, req: PermissionCheck):
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
async def resolve_open_id(user_id: int, req: ResolveOpenIdRequest):
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
async def rebuild_load():
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
