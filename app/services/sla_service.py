"""SLA 时效管理服务。"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import yaml

from sqlalchemy import case, select

from app.db.models.ticket import Ticket
from app.db.session import session_scope


SLA_PATH = Path(__file__).parent.parent / "config" / "sla_rules.yaml"


def load_rules() -> Dict:
    if not SLA_PATH.exists():
        return {"sla_rules": {}, "warning_ratio": 0.3}
    with open(SLA_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"sla_rules": {}, "warning_ratio": 0.3}


def write_rules(rules: Dict) -> None:
    """回写 sla_rules.yaml。"""
    import shutil as _sh
    import yaml as _yaml

    if SLA_PATH.exists():
        _sh.copy2(SLA_PATH, str(SLA_PATH) + ".bak")

    with open(SLA_PATH, "w", encoding="utf-8", newline="\n") as f:
        _yaml.safe_dump(
            rules, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def compute_deadline(ticket_type: str, urgent: bool = False,
                     created_at: Optional[datetime] = None) -> datetime:
    rules = load_rules().get("sla_rules", {})
    rule = rules.get(ticket_type, rules.get("default", {"urgent": 4, "normal": 24}))
    if not isinstance(rule, dict):
        rule = {"urgent": 4, "normal": 24}
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


def get_ticket_sla_info(ticket: Ticket) -> Dict:
    """返回给前端的 SLA 信息（倒计时等）。"""
    if not ticket.sla_deadline or not ticket.created_at:
        return {
            "sla_deadline": None,
            "sla_status": "normal",
            "remain_seconds": None,
            "total_seconds": None,
            "elapsed_ratio": 0.0,
        }

    now = datetime.utcnow()
    total = (ticket.sla_deadline - ticket.created_at).total_seconds()
    remain = (ticket.sla_deadline - now).total_seconds()
    status = check_ticket_sla(ticket)

    return {
        "sla_deadline": ticket.sla_deadline.isoformat(),
        "sla_status": status,
        "remain_seconds": int(remain),
        "total_seconds": int(total),
        "elapsed_ratio": round(max(0.0, min(1.0, 1 - remain / total)), 4) if total > 0 else 0.0,
    }


# ============================================================
# 扫描 + 通知
# ============================================================
def _notify_sla(ticket: Ticket, new_status: str) -> None:
    """发飞书通知（通过 notify/notifier.py）。"""
    try:
        from app.notify.notifier import send as notify
        from app.db.models.user import User

        # 找工程师的飞书 open_id
        target = ticket.assigned_to or "unknown"
        feishu_id = ""

        with session_scope() as s:
            u = s.execute(
                select(User).where(User.name == target)
            ).scalar_one_or_none()
            if u:
                feishu_id = u.feishu_open_id or ""

        # 找主管（用于超时告警）
        supervisor_ids = []
        with session_scope() as s:
            sups = s.execute(
                select(User).where(User.role == "supervisor")
            ).scalars().all()
            supervisor_ids = [x.feishu_open_id for x in sups if x.feishu_open_id]

        if new_status == "warning":
            content = (
                f"工单 {ticket.ticket_id} 即将超时\n"
                f"设备：{ticket.device_model or '-'} 故障码：{ticket.error_code or '-'}\n"
                f"截止：{ticket.sla_deadline}\n"
                f"请尽快处理。"
            )
            notify(
                target=feishu_id or target,
                event="sla_warning",
                title=f"🟠 SLA 预警 - {ticket.ticket_id}",
                content=content,
                channel="feishu",
            )
        elif new_status == "overdue":
            content = (
                f"工单 {ticket.ticket_id} 已超时\n"
                f"设备：{ticket.device_model or '-'} 故障码：{ticket.error_code or '-'}\n"
                f"截止：{ticket.sla_deadline}\n"
                f"负责人：{target}\n"
                f"请立即处理或改派。"
            )
            notify(
                target=feishu_id or target,
                event="sla_overdue",
                title=f"🔴 SLA 超时 - {ticket.ticket_id}",
                content=content,
                channel="feishu",
            )
            # 同时通知所有主管
            for sid in supervisor_ids:
                notify(
                    target=sid,
                    event="sla_overdue_supervisor",
                    title=f"🔴 工单超时 - {ticket.ticket_id}",
                    content=content,
                    channel="feishu",
                )
    except Exception as e:
        print(f"[SLA] notify failed: {e}")


def scan_all_tickets() -> dict:
    """扫描所有未关闭工单，更新 SLA 状态并通知。"""
    stats = {"normal": 0, "warning": 0, "overdue": 0, "checked": 0, "notified": 0}
    with session_scope() as s:
        rows = s.execute(
            select(Ticket).where(Ticket.status.notin_(["closed", "cancelled", "resolved"]))
        ).scalars().all()

        for t in rows:
            stats["checked"] += 1
            new_status = check_ticket_sla(t)
            stats[new_status] += 1
            old_status = t.sla_status or "normal"

            # 只在状态变化时通知（避免重复轰炸）
            if old_status != new_status:
                t.sla_status = new_status
                # 跳过 normal -> 只在 warning / overdue 时通知
                if new_status in ("warning", "overdue"):
                    stats["notified"] += 1
                    # 在 session 外发通知
                    _notify_sla(t, new_status)

    return stats


def get_sla_summary() -> dict:
    """SLA 汇总。"""
    from sqlalchemy import func, select
    with session_scope() as s:
        rows = s.execute(
            select(Ticket.sla_status, func.count(Ticket.ticket_id))
            .group_by(Ticket.sla_status)
        ).all()
        dist = {r[0] or "normal": r[1] for r in rows}
        total = sum(dist.values())
        closed = s.execute(
            select(func.count(Ticket.ticket_id))
            .where(Ticket.status.in_(["resolved", "closed"]))
        ).scalar() or 0
        return {
            "distribution": dist,
            "total": total,
            "overdue": dist.get("overdue", 0),
            "warning": dist.get("warning", 0),
            "normal": dist.get("normal", 0),
            "achieved": closed,
            "achievement_rate": round((closed / total * 100) if total else 0, 1),
        }


def get_sla_tickets() -> dict:
    """返回所有未关闭工单 + SLA 倒计时（给前端用）。"""
    out = []
    with session_scope() as s:
        rows = s.execute(
            select(Ticket)
            .where(Ticket.status.notin_(["closed", "cancelled"]))
            .order_by(
                case((Ticket.sla_deadline.is_(None), 1), else_=0),
                Ticket.sla_deadline.asc(),
            )
            .limit(50)
        ).scalars().all()
        for t in rows:
            info = get_ticket_sla_info(t)
            out.append({
                "ticket_id": t.ticket_id,
                "status": t.status,
                "assigned_to": t.assigned_to,
                "device_model": t.device_model,
                "error_code": t.error_code,
                "ticket_type": t.ticket_type or "repair",
                **info,
            })
    return {"total": len(out), "items": out}
