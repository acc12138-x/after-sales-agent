"""SLA 时效管理服务。"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import yaml

from app.db.models.ticket import Ticket
from app.db.session import session_scope


SLA_PATH = Path(__file__).parent.parent / "config" / "sla_rules.yaml"


def load_rules() -> Dict:
    if not SLA_PATH.exists():
        return {"sla_rules": {}, "warning_ratio": 0.3}
    with open(SLA_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"sla_rules": {}, "warning_ratio": 0.3}


def compute_deadline(ticket_type: str, urgent: bool = False, created_at: datetime = None) -> datetime:
    """根据工单类型 + 紧急度，计算 SLA 截止时间。"""
    rules = load_rules().get("sla_rules", {})
    rule = rules.get(ticket_type, rules.get("default", {"urgent": 4, "normal": 24}))
    hours = rule.get("urgent" if urgent else "normal", 24)
    base = created_at or datetime.utcnow()
    return base + timedelta(hours=hours)


def check_ticket_sla(ticket: Ticket) -> str:
    """返回：normal / warning / overdue"""
    if not ticket.sla_deadline:
        return "normal"
    now = datetime.utcnow()
    if now > ticket.sla_deadline:
        return "overdue"
    total = (ticket.sla_deadline - ticket.created_at).total_seconds()
    remain = (ticket.sla_deadline - now).total_seconds()
    ratio = load_rules().get("warning_ratio", 0.3)
    if total > 0 and remain / total <= ratio:
        return "warning"
    return "normal"


def scan_all_tickets() -> dict:
    """扫描所有未关闭工单，更新 SLA 状态。"""
    stats = {"normal": 0, "warning": 0, "overdue": 0, "checked": 0}
    with session_scope() as s:
        # 只看未关闭的
        from sqlalchemy import select
        rows = s.execute(
            select(Ticket).where(Ticket.status.notin_(["closed", "cancelled", "resolved"]))
        ).scalars().all()
        for t in rows:
            stats["checked"] += 1
            new_status = check_ticket_sla(t)
            stats[new_status] += 1
            if t.sla_status != new_status:
                t.sla_status = new_status
    return stats


def get_sla_summary() -> dict:
    """SLA 汇总：各状态数量 + 达成率。"""
    from sqlalchemy import func, select
    with session_scope() as s:
        rows = s.execute(
            select(Ticket.sla_status, func.count(Ticket.ticket_id))
            .group_by(Ticket.sla_status)
        ).all()
        dist = {r[0] or "normal": r[1] for r in rows}
        total = sum(dist.values())
        # 已解决/关闭的算达标
        closed = s.execute(
            select(func.count(Ticket.ticket_id))
            .where(Ticket.status.in_(["resolved", "closed"]))
        ).scalar() or 0
        achieved = closed
        return {
            "distribution": dist,
            "total": total,
            "overdue": dist.get("overdue", 0),
            "warning": dist.get("warning", 0),
            "normal": dist.get("normal", 0),
            "achieved": achieved,
            "achievement_rate": round((achieved / total * 100) if total else 0, 1),
        }
