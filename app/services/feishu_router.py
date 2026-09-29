"""飞书消息路由：事件 → 群 webhook。

- 读 config/feishu_routes.yaml
- 有 webhook 时 POST 到飞书
- 无 webhook 时降级为只记 notifications 表
- 单机器人 + 多群策略
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List

import yaml
import httpx

from app.db.models.notification import Notification
from app.db.session import session_scope

CONFIG_PATH = Path(__file__).parent.parent / "config" / "feishu_routes.yaml"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"channels": {}, "routes": {}}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"channels": {}, "routes": {}}


def _record_notification(channel: str, event: str, title: str, content: str, status: str, error: str = ""):
    """写入 notifications 表，作为审计。"""
    try:
        with session_scope() as s:
            s.add(Notification(
                channel=f"feishu:{channel}",
                target=channel,
                event=event,
                title=title,
                content=content,
                status=status,
                error=error,
            ))
    except Exception:
        pass


def _post_to_feishu(webhook: str, title: str, content: str, at_all: bool = False) -> tuple[bool, str]:
    """POST 到飞书 webhook。返回 (success, error)。"""
    if not webhook:
        return False, "webhook 未配置"

    # 飞书消息卡片格式
    text = f"{title}\n{content}"
    if at_all:
        text = "<at user_id=\"all\">所有人</at>\n" + text

    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }

    try:
        r = httpx.post(webhook, json=payload, timeout=10, trust_env=False)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 0 or d.get("StatusCode") == 0:
                return True, ""
            return False, str(d)[:200]
        return False, f"HTTP {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return False, str(e)[:200]


def dispatch(event: str, title: str, content: str) -> Dict:
    """按事件路由到群。返回每群的发送结果。"""
    cfg = _load_config()
    channels = cfg.get("channels", {})
    routes = cfg.get("routes", {})

    targets = routes.get(event, [])
    if not targets:
        return {"event": event, "targets": [], "results": [], "note": "无路由配置"}

    results = []
    for ch_name in targets:
        ch = channels.get(ch_name, {})
        webhook = ch.get("webhook", "")
        at_all = ch.get("at_all", False)

        if webhook:
            ok, err = _post_to_feishu(webhook, title, content, at_all)
        else:
            ok, err = False, "webhook 未配置（开发模式）"

        _record_notification(
            channel=ch_name,
            event=event,
            title=title,
            content=content,
            status="sent" if ok else "pending",
            error=err,
        )

        results.append({
            "channel": ch_name,
            "label": ch.get("label", ch_name),
            "webhook_set": bool(webhook),
            "sent": ok,
            "error": err,
        })

    return {"event": event, "targets": targets, "results": results}


def list_config() -> Dict:
    """查看当前配置（脱敏 webhook）。"""
    cfg = _load_config()
    channels = cfg.get("channels", {})
    routes = cfg.get("routes", {})

    safe_channels = {}
    for k, v in channels.items():
        safe_channels[k] = {
            "label": v.get("label", k),
            "webhook_set": bool(v.get("webhook", "")),
            "at_all": v.get("at_all", False),
        }
    return {"channels": safe_channels, "routes": routes}


def reload_config() -> Dict:
    """重新读 yaml（当前实现无缓存，直接返回）。"""
    return list_config()
