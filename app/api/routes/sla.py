"""SLA 时效管理 API。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.sla_service import get_sla_summary, scan_all_tickets, load_rules

router = APIRouter(prefix="/sla", tags=["sla"])


@router.get("/summary")
async def summary():
    return get_sla_summary()


@router.post("/scan")
async def scan():
    """手动触发一次 SLA 扫描。"""
    return scan_all_tickets()


@router.get("/rules")
async def rules():
    return load_rules()
