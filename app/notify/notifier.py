"""通知工具：写库 + 真发飞书。

- 环境变量 NOTIFY_REAL_SEND=0 时只写库（调试用）
- 默认真发飞书（仅当 target 是 ou_/oc_ 开头的有效 ID）
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


def send(target, event, title="", content="", channel="feishu", chat_id=""):
    """写库 + （可选）真发飞书。

    返回：True/False 表示飞书是否发送成功（未真发时返回 True）
    """
    real_send = os.environ.get("NOTIFY_REAL_SEND", "1").lower() in ("1", "true", "yes")

    # 非 feishu 渠道：只写库
    if channel != "feishu" or not real_send:
        _write_db(target, event, title, content, channel, "sent")
        return True

    # target 不是有效飞书 ID：只写库，标记未发送原因
    if not target or not (target.startswith("ou_") or target.startswith("oc_")):
        _write_db(target, event, title, content, channel, "sent",
                  error="target 非飞书 ID，未发送")
        return True

    # 真发飞书
    try:
        from app.integrations.feishu_client import send_smart
        ok, err = send_smart(target, title, content, chat_id=chat_id)
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
