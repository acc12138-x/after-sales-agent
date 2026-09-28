"""通知工具（模拟）。真实环境会调飞书 API / 短信网关。"""
from __future__ import annotations
from typing import Optional

from app.db.models.notification import Notification
from app.db.session import session_scope


def send(
    target: str,
    event: str,
    title: str = "",
    content: str = "",
    channel: str = "feishu",
) -> None:
    """记录通知。失败不阻塞主流程。"""
    try:
        with session_scope() as s:
            s.add(Notification(
                channel=channel,
                target=target,
                event=event,
                title=title,
                content=content,
                status="sent",
            ))
    except Exception:
        pass
