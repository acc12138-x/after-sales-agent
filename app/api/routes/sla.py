"""SLA 时效管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_permission
from app.services.sla_service import (
    get_sla_summary, get_sla_tickets, load_rules, scan_all_tickets, write_rules,
)

router = APIRouter(prefix="/sla", tags=["sla"])

# 查看倒计时/规则：sla.view；触发扫描/改规则：sla.edit
_sla_view = require_permission("sla.view")
_sla_edit = require_permission("sla.edit")


@router.get("/summary")
async def summary(user: dict = Depends(_sla_view)):
    return get_sla_summary()


@router.post("/scan")
async def scan(user: dict = Depends(_sla_edit)):
    """手动触发一次 SLA 扫描。"""
    return scan_all_tickets()


@router.get("/tickets")
async def tickets(user: dict = Depends(_sla_view)):
    """所有未关闭工单的 SLA 倒计时。"""
    return get_sla_tickets()


@router.get("/rules")
async def rules(user: dict = Depends(_sla_view)):
    return load_rules()


# ============================================================
# 规则编辑
# ============================================================
from pydantic import BaseModel
from typing import Dict


class RuleItem(BaseModel):
    urgent: int
    normal: int
    label: str = ""


class RulesUpdate(BaseModel):
    sla_rules: Dict[str, RuleItem]
    warning_ratio: float = 0.3


@router.put("/rules")
async def update_rules(payload: RulesUpdate, user: dict = Depends(_sla_edit)):
    """更新 SLA 规则。"""
    new_data = {
        "sla_rules": {
            k: v.dict() for k, v in payload.sla_rules.items()
        },
        "warning_ratio": payload.warning_ratio,
    }
    write_rules(new_data)
    return {"status": "ok", "rules": new_data}
