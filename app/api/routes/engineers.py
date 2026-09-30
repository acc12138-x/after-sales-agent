"""工程师管理 API（统一读 users 表，role=engineer）"""
from __future__ import annotations
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api.deps import require_permission
from app.api.schemas.models import EngineerCreate, EngineerResponse, EngineerUpdate
from app.db.models.user import User
from app.db.session import session_scope

router = APIRouter(prefix="/engineers", tags=["engineers"])

# 工程师页是人员管理的旧入口，权限与 users 保持一致
_e_view = require_permission("user.view")
_e_edit = require_permission("user.edit")


def _next_user_id(s) -> str:
    """生成下一个唯一 user_id（U0001 格式）"""
    ids = s.execute(select(User.user_id)).scalars().all()
    max_num = 0
    for uid in ids:
        if uid and uid.startswith("U"):
            try:
                n = int(uid[1:])
                max_num = max(max_num, n)
            except ValueError:
                pass
    return f"U{max_num + 1:04d}"


def _to_resp(u: User) -> dict:
    """User -> EngineerResponse（前端结构兼容）"""
    return {
        "id": u.id,
        "name": u.name,
        "skills": u.skill_list,
        "region": u.region or "",
        "phone": u.phone or "",
        "feishu_open_id": u.feishu_open_id or "",
        "feishu_chat_id": u.feishu_chat_id or "",
        "status": u.status or "online",
        "current_load": u.current_load or 0,
        "max_load": u.max_load or 10,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("", response_model=List[EngineerResponse])
async def list_engineers(user: dict = Depends(_e_view)):
    with session_scope() as s:
        rows = s.execute(
            select(User).where(User.role == "engineer")
            .order_by(User.current_load, User.id)
        ).scalars().all()
        return [_to_resp(u) for u in rows]


@router.post("", response_model=EngineerResponse)
async def create_engineer(req: EngineerCreate,
                          user: dict = Depends(_e_edit)):
    with session_scope() as s:
        exists = s.execute(
            select(User).where(User.name == req.name)
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail=f"人员 {req.name} 已存在")

        uid = _next_user_id(s)

        u = User(
            user_id=uid,
            name=req.name,
            role="engineer",
            job="维修",
            skills=json.dumps(req.skills, ensure_ascii=False),
            region=req.region or "",
            phone=req.phone or "",
            feishu_open_id=req.feishu_open_id or "",
            feishu_chat_id=req.feishu_chat_id or "",
            status=req.status or "online",
            current_load=0,
            max_load=req.max_load or 10,
            dept="",
            permissions="{}",
        )
        s.add(u)
        s.flush()
        return _to_resp(u)


@router.put("/{engineer_id}", response_model=EngineerResponse)
async def update_engineer(engineer_id: int, req: EngineerUpdate,
                          user: dict = Depends(_e_edit)):
    with session_scope() as s:
        u = s.get(User, engineer_id)
        if u is None or u.role != "engineer":
            raise HTTPException(status_code=404, detail="工程师不存在")

        if req.name is not None:
            u.name = req.name
        if req.skills is not None:
            u.skills = json.dumps(req.skills, ensure_ascii=False)
        if req.region is not None:
            u.region = req.region
        if req.phone is not None:
            u.phone = req.phone
        if req.feishu_open_id is not None:
            u.feishu_open_id = req.feishu_open_id
        if req.feishu_chat_id is not None:
            u.feishu_chat_id = req.feishu_chat_id
        if req.status is not None:
            u.status = req.status
        if req.max_load is not None:
            u.max_load = req.max_load
        s.flush()
        return _to_resp(u)


@router.delete("/{engineer_id}")
async def delete_engineer(engineer_id: int, user: dict = Depends(_e_edit)):
    with session_scope() as s:
        u = s.get(User, engineer_id)
        if u is None or u.role != "engineer":
            raise HTTPException(status_code=404, detail="工程师不存在")
        if (u.current_load or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该工程师还有 {u.current_load} 个进行中工单，无法删除",
            )
        s.delete(u)
    return {"deleted": engineer_id}


@router.post("/{engineer_id}/toggle-status")
async def toggle_status(engineer_id: int, user: dict = Depends(_e_edit)):
    with session_scope() as s:
        u = s.get(User, engineer_id)
        if u is None or u.role != "engineer":
            raise HTTPException(status_code=404, detail="工程师不存在")
        u.status = "offline" if u.status == "online" else "online"
        s.flush()
        return {"id": u.id, "status": u.status}


@router.post("/rebuild-load")
async def rebuild_load(user: dict = Depends(_e_edit)):
    """从 tickets 表重建所有工程师的当前负载。"""
    from app.db.models.ticket import Ticket

    with session_scope() as s:
        rows = s.execute(
            select(Ticket.assigned_to, func.count(Ticket.ticket_id))
            .where(Ticket.status.in_(["assigned", "accepted", "in_progress"]))
            .group_by(Ticket.assigned_to)
        ).all()
        active_counts = {r[0]: r[1] for r in rows if r[0]}

        engineers = s.execute(
            select(User).where(User.role == "engineer")
        ).scalars().all()
        updated = []
        for u in engineers:
            new_load = active_counts.get(u.name, 0)
            old = u.current_load
            u.current_load = new_load
            updated.append({"name": u.name, "old": old, "new": new_load})

        return {"updated": updated, "active_tickets": sum(active_counts.values())}
