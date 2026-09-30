"""飞书消息路由：事件 -> 用户/群。

流程：
1. 收到事件（如 ticket_assigned）
2. 按 event 决定发给哪些角色的人
3. 查 users 表拿到所有 open_id
4. 通过飞书应用私聊发送
5. 群 webhook 作为补充广播
6. 记录 notifications
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List

import yaml
from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.user import User
from app.db.session import session_scope
from app.integrations.feishu_client import (
    send_private_markdown, send_webhook, send_smart,
)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "feishu_routes.yaml"


# ============================================================
# 事件 → 目标角色（决定私聊给谁）
# ============================================================
EVENT_TO_ROLES = {
    # 工单相关
    "ticket_assigned":        ["engineer"],          # 工程师
    "ticket_accepted":        ["supervisor"],        # 主管知会
    "ticket_rejected":        ["supervisor", "engineer"],   # 主管 + 工程师
    "ticket_resolved":        ["supervisor"],        # 主管审批
    "ticket_escalated":       ["supervisor"],

    # 退款相关
    "refund_created":         ["supervisor"],
    "refund_pending":         ["supervisor"],        # 待审批私聊主管
    "refund_approved":        ["agent"],             # 客服通知客户
    "refund_rejected":        ["agent"],

    # SLA
    "sla_warning":            ["engineer"],          # 预警私聊工程师
    "sla_overdue":            ["engineer", "supervisor"],   # 超时工程师 + 主管
    "sla_overdue_supervisor": ["supervisor"],

    # 客户
    "customer_created":       ["agent"],
    "complaint":              ["supervisor"],

    # HITL
    "hitl_request":           ["supervisor"],
}


# ============================================================
# 事件 → 群（决定广播到哪些群）
# ============================================================
EVENT_TO_GROUPS = {
    "ticket_assigned":        [],
    "ticket_accepted":        ["engineer_group"],
    "ticket_rejected":        ["engineer_group"],
    "ticket_resolved":        ["supervisor_group"],
    "ticket_escalated":       ["supervisor_group"],

    "refund_created":         ["supervisor_group"],
    "refund_pending":         ["supervisor_group"],
    "refund_approved":        [],
    "refund_rejected":        [],

    "sla_warning":            ["sla_group"],
    "sla_overdue":            ["sla_group", "supervisor_group"],
    "sla_overdue_supervisor": ["supervisor_group"],
}


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"channels": {}, "routes": {}}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"channels": {}, "routes": {}}


def _record_notification(channel: str, target: str, event: str,
                        title: str, content: str, status: str, error: str = ""):
    try:
        with session_scope() as s:
            s.add(Notification(
                channel=channel,
                target=target,
                event=event,
                title=title,
                content=content,
                status=status,
                error=error,
            ))
    except Exception:
        pass


def _get_users_by_roles(roles: List[str]) -> List[dict]:
    """按角色查用户，返回含 open_id 的列表。"""
    if not roles:
        return []
    with session_scope() as s:
        rows = s.execute(
            select(User).where(User.role.in_(roles), User.status == "online")
        ).scalars().all()
        return [
            {"id": u.id, "name": u.name, "role": u.role,
             "open_id": u.feishu_open_id or "",
             "chat_id": getattr(u, "feishu_chat_id", "") or ""}
            for u in rows
        ]


def dispatch(event: str, title: str, content: str,
             extra_roles: List[str] = None,
             extra_open_ids: List[str] = None,
             target_name: str = "") -> Dict:
    """
    分发事件：
    1. 按角色私聊给相关人员
    2. 按事件广播到群
    3. 记录通知
    """
    cfg = _load_config()
    channels = cfg.get("channels", {})

    result = {
        "event": event,
        "private": [],   # 私聊结果
        "group": [],     # 群结果
    }

    # ============================================================
    # 1. 私聊给角色对应的人
    # ============================================================
    roles = list(EVENT_TO_ROLES.get(event, []))
    if extra_roles:
        roles.extend(extra_roles)
    roles = list(set(roles))

    targets = _get_users_by_roles(roles)
    if target_name:
        # 只发给指定人
        targets = [t for t in targets if t["name"] == target_name]

    for u in targets:
        oid = u["open_id"]
        if not oid:
            result["private"].append({
                "name": u["name"], "role": u["role"],
                "sent": False, "error": "未配置 open_id",
            })
            continue

        # 智能发送：优先 chat_id（飞书限制 open_id 主动发单聊）
        cid = u.get("chat_id", "") or ""
        ok, err = send_smart(oid, title, content, chat_id=cid)
        _record_notification(
            channel="feishu_private",
            target=u["name"],
            event=event,
            title=title,
            content=content,
            status="sent" if ok else "failed",
            error=err,
        )
        result["private"].append({
            "name": u["name"], "role": u["role"],
            "sent": ok, "error": err,
        })

    # 额外的 open_id（不在 users 表里也发）
    for oid in (extra_open_ids or []):
        ok, err = send_private_markdown(oid, title, content)
        _record_notification(
            channel="feishu_private",
            target=oid,
            event=event,
            title=title,
            content=content,
            status="sent" if ok else "failed",
            error=err,
        )
        result["private"].append({
            "name": oid, "role": "extra",
            "sent": ok, "error": err,
        })

    # ============================================================
    # 2. 广播到群
    # ============================================================
    group_names = EVENT_TO_GROUPS.get(event, [])
    for gname in group_names:
        ch = channels.get(gname, {})
        webhook = ch.get("webhook", "")
        at_all = ch.get("at_all", False)
        if not webhook:
            result["group"].append({
                "channel": gname, "label": ch.get("label", gname),
                "sent": False, "error": "webhook 未配置",
            })
            continue
        ok, err = send_webhook(webhook, f"{title}\n{content}", at_all)
        _record_notification(
            channel=f"feishu_group:{gname}",
            target=gname,
            event=event,
            title=title,
            content=content,
            status="sent" if ok else "failed",
            error=err,
        )
        result["group"].append({
            "channel": gname, "label": ch.get("label", gname),
            "sent": ok, "error": err,
        })

    return result


def dispatch_to_user(user_id: int, title: str, content: str,
                    event: str = "manual_test") -> Dict:
    """发给指定用户（后台手动测试用）。"""
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            return {"ok": False, "error": "用户不存在"}
        oid = u.feishu_open_id or ""
        name = u.name

    if not oid:
        return {"ok": False, "error": f"{name} 未配置飞书 ID（open_id 或 chat_id）"}

    ok, err = send_smart(oid, title, content)
    _record_notification(
        channel="feishu_private",
        target=name,
        event=event,
        title=title,
        content=content,
        status="sent" if ok else "failed",
        error=err,
    )
    return {"ok": ok, "error": err, "to": name, "target": oid[:24] + "..."}


def list_config() -> Dict:
    cfg = _load_config()
    channels = cfg.get("channels", {})
    safe_channels = {}
    for k, v in channels.items():
        safe_channels[k] = {
            "label": v.get("label", k),
            "webhook_set": bool(v.get("webhook", "")),
            "at_all": v.get("at_all", False),
        }
    return {
        "channels": safe_channels,
        "event_to_roles": EVENT_TO_ROLES,
        "event_to_groups": EVENT_TO_GROUPS,
    }
