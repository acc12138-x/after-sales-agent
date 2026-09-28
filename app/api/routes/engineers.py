"""工程师管理 API。"""
from __future__ import annotations
import json
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas.models import EngineerCreate, EngineerResponse, EngineerUpdate
from app.db.models.engineer import Engineer
from app.db.session import session_scope

router = APIRouter(prefix="/engineers", tags=["engineers"])


def _to_resp(e: Engineer) -> EngineerResponse:
    d = e.to_dict()
    return EngineerResponse(**d)


@router.get("", response_model=List[EngineerResponse])
async def list_engineers():
    with session_scope() as s:
        rows = s.execute(select(Engineer).order_by(Engineer.current_load, Engineer.id)).scalars().all()
        return [_to_resp(e) for e in rows]


@router.post("", response_model=EngineerResponse)
async def create_engineer(req: EngineerCreate):
    with session_scope() as s:
        exists = s.execute(select(Engineer).where(Engineer.name == req.name)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail=f"工程师 {req.name} 已存在")

        e = Engineer(
            name=req.name,
            skills=json.dumps(req.skills, ensure_ascii=False),
            region=req.region,
            phone=req.phone,
            feishu_open_id=req.feishu_open_id,
            status=req.status,
            max_load=req.max_load,
            current_load=0,
        )
        s.add(e)
        s.flush()
        return _to_resp(e)


@router.put("/{engineer_id}", response_model=EngineerResponse)
async def update_engineer(engineer_id: int, req: EngineerUpdate):
    with session_scope() as s:
        e = s.get(Engineer, engineer_id)
        if e is None:
            raise HTTPException(status_code=404, detail="工程师不存在")

        if req.name is not None:
            e.name = req.name
        if req.skills is not None:
            e.skills = json.dumps(req.skills, ensure_ascii=False)
        if req.region is not None:
            e.region = req.region
        if req.phone is not None:
            e.phone = req.phone
        if req.feishu_open_id is not None:
            e.feishu_open_id = req.feishu_open_id
        if req.status is not None:
            e.status = req.status
        if req.max_load is not None:
            e.max_load = req.max_load
        s.flush()
        return _to_resp(e)


@router.delete("/{engineer_id}")
async def delete_engineer(engineer_id: int):
    with session_scope() as s:
        e = s.get(Engineer, engineer_id)
        if e is None:
            raise HTTPException(status_code=404, detail="工程师不存在")
        if e.current_load > 0:
            raise HTTPException(status_code=400, detail=f"该工程师还有 {e.current_load} 个进行中工单，无法删除")
        s.delete(e)
    return {"deleted": engineer_id}


@router.post("/{engineer_id}/toggle-status")
async def toggle_status(engineer_id: int):
    """在线/离线切换。"""
    with session_scope() as s:
        e = s.get(Engineer, engineer_id)
        if e is None:
            raise HTTPException(status_code=404, detail="工程师不存在")
        e.status = "offline" if e.status == "online" else "online"
        s.flush()
        return {"id": e.id, "status": e.status}
