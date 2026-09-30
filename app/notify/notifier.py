"""通知工具：写库 + 真发飞书。

- 环境变量 NOTIFY_REAL_SEND=0 时只写库（调试用），默认真发
- target 支持三种形式：
    ou_xxx  → 飞书 open_id（私聊）
    oc_xxx  → 飞书 chat_id（群）
    其它    → 按「人员姓名」在 users 表解析出该人绑定的 open_id / chat_id

解析不到目标时记录 status="failed"，不再误记为 "sent"。
"""
from __future__ import annotations
import os

from app.db.models.notification import Notification
from app.db.session import session_scope


def _write_db(target, event, title, content, channel, status, error=""):
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
    except Exception as e:
        print(f"[NOTIFY] db write failed: {e}")


def resolve_target(target: str) -> tuple[str, str]:
    """把 target 解析成 (open_id, chat_id)。

    - `ou_` / `oc_` 前缀：原样识别
    - 其它（工程师姓名等）：查 users 表，取其绑定的飞书 ID
    - 解析不到：返回 ("", "")
    """
    if not target:
        return "", ""
    if target.startswith("ou_"):
        return target, ""
    if target.startswith("oc_"):
        return "", target
    try:
        from sqlalchemy import select

        from app.db.models.user import User

        with session_scope() as s:
            u = s.execute(
                select(User).where(User.name == target)
            ).scalars().first()
            if u is None:
                return "", ""
            return (u.feishu_open_id or ""), (u.feishu_chat_id or "")
    except Exception as e:
        print(f"[NOTIFY] resolve target failed: {e}")
        return "", ""


def send(target, event, title="", content="", channel="feishu", chat_id=""):
    """写库 + （可选）真发飞书。

    返回：True/False 表示飞书是否发送成功（未真发时返回 True）
    """
    real_send = os.environ.get("NOTIFY_REAL_SEND", "1").lower() in ("1", "true", "yes")

    # 非 feishu 渠道：只写库
    if channel != "feishu" or not real_send:
        _write_db(target, event, title, content, channel, "sent")
        return True

    # 解析目标：既支持直接给 open_id / chat_id，也支持给人员姓名
    open_id, resolved_chat_id = resolve_target(target)
    if not open_id and not resolved_chat_id:
        _write_db(target, event, title, content, channel, "failed",
                  error="无法解析飞书目标：既不是 ou_/oc_，也未在人员表中匹配到该姓名")
        print(f"[NOTIFY] 目标无法解析，未发送：target={target!r} event={event}")
        return False

    # 真发飞书
    try:
        from app.integrations.feishu_client import send_smart
        ok, err = send_smart(
            open_id or target, title, content,
            chat_id=chat_id or resolved_chat_id,
        )
        _write_db(target, event, title, content, channel,
                  "sent" if ok else "failed",
                  err)
        if not ok:
            print(f"[NOTIFY] feishu send failed: {err}")
        return ok
    except Exception as e:
        _write_db(target, event, title, content, channel, "failed", str(e)[:200])
        print(f"[NOTIFY] send exception: {e}")
        return False
