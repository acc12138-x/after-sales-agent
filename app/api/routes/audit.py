"""审计日志 + 通知记录 API。"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, desc

from app.db.models.audit_log import AuditLog
from app.db.models.notification import Notification
from app.db.session import session_scope

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/audit")
async def list_audit(
    limit: int = Query(100, le=1000),
    action: Optional[str] = None,
    target_id: Optional[str] = None,
):
    """审计日志列表（倒序）。"""
    with session_scope() as s:
        q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        if action:
            q = q.where(AuditLog.action.like(f"%{action}%"))
        if target_id:
            q = q.where(AuditLog.target_id == target_id)
        rows = s.execute(q).scalars().all()
        return {"total": len(rows), "items": [r.to_dict() for r in rows]}


@router.get("/notifications")
async def list_notifications(
    limit: int = Query(100, le=1000),
    channel: Optional[str] = None,
    event: Optional[str] = None,
    target: Optional[str] = None,
):
    """通知记录列表（倒序）。"""
    with session_scope() as s:
        q = select(Notification).order_by(desc(Notification.created_at)).limit(limit)
        if channel:
            q = q.where(Notification.channel == channel)
        if event:
            q = q.where(Notification.event.like(f"%{event}%"))
        if target:
            q = q.where(Notification.target.like(f"%{target}%"))
        rows = s.execute(q).scalars().all()
        return {"total": len(rows), "items": [r.to_dict() for r in rows]}


@router.get("/audit/stats")
async def audit_stats():
    """审计日志统计：按 action 分组。"""
    from sqlalchemy import func
    with session_scope() as s:
        rows = s.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(20)
        ).all()
        return {"items": [{"action": r[0], "count": r[1]} for r in rows]}


@router.get("/notifications/stats")
async def notif_stats():
    from sqlalchemy import func
    with session_scope() as s:
        rows = s.execute(
            select(Notification.event, func.count(Notification.id))
            .group_by(Notification.event)
            .order_by(func.count(Notification.id).desc())
            .limit(20)
        ).all()
        return {"items": [{"event": r[0], "count": r[1]} for r in rows]}
