"""SLA 时效管理 API。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.sla_service import (
    get_sla_summary, get_sla_tickets, load_rules, scan_all_tickets, write_rules,
)

router = APIRouter(prefix="/sla", tags=["sla"])


@router.get("/summary")
async def summary():
    return get_sla_summary()


@router.post("/scan")
async def scan():
    """手动触发一次 SLA 扫描。"""
    return scan_all_tickets()


@router.get("/tickets")
async def tickets():
    """所有未关闭工单的 SLA 倒计时。"""
    return get_sla_tickets()


@router.get("/rules")
async def rules():
    return load_rules()


# ============================================================
# 规则编辑
# ============================================================
from pydantic import BaseModel
from typing import Any, Dict


class RuleItem(BaseModel):
    urgent: int
    normal: int
    label: str = ""


class RulesUpdate(BaseModel):
    sla_rules: Dict[str, RuleItem]
    warning_ratio: float = 0.3


@router.put("/rules")
async def update_rules(payload: RulesUpdate):
    """更新 SLA 规则。"""
    new_data = {
        "sla_rules": {
            k: v.dict() for k, v in payload.sla_rules.items()
        },
        "warning_ratio": payload.warning_ratio,
    }
    write_rules(new_data)
    return {"status": "ok", "rules": new_data}
