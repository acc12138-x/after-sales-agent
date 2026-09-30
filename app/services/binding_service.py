"""飞书身份绑定服务。

三个动作：
- record_unbound：收到陌生 open_id 时登记到待绑定表（已绑定的忽略）
- list_pending  ：列出待绑定
- bind / dismiss：绑定到某个 User，或忽略

所有写入失败都静默处理，绝不阻塞对话主流程。
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from app.db.models.pending_binding import PendingBinding
from app.db.models.user import User
from app.db.session import session_scope


def find_user_by_open_id(open_id: str) -> Optional[dict]:
    """已绑定该 open_id 的人员（不存在返回 None）。"""
    if not open_id:
        return None
    with session_scope() as s:
        u = s.execute(
            select(User).where(User.feishu_open_id == open_id)
        ).scalars().first()
        return u.to_dict() if u else None


def record_unbound(open_id: str, chat_id: str = "", text: str = "") -> bool:
    """登记一个尚未绑定到任何 User 的 open_id。

    返回 True 表示写入了待绑定表；已绑定或写库失败返回 False。
    """
    if not open_id:
        return False
    try:
        with session_scope() as s:
            bound = s.execute(
                select(User).where(User.feishu_open_id == open_id)
            ).scalars().first()
            if bound is not None:
                return False

            row = s.get(PendingBinding, open_id)
            now = datetime.now()
            if row is None:
                s.add(PendingBinding(
                    open_id=open_id,
                    chat_id=chat_id or "",
                    last_text=(text or "")[:256],
                    message_count=1,
                    first_seen=now,
                    last_seen=now,
                ))
            else:
                row.chat_id = chat_id or row.chat_id or ""
                row.last_text = (text or row.last_text or "")[:256]
                row.message_count = (row.message_count or 0) + 1
                row.last_seen = now
        return True
    except Exception as e:
        print(f"[BIND] record_unbound failed: {e}")
        return False


def list_pending() -> List[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(PendingBinding).order_by(PendingBinding.last_seen.desc())
        ).scalars().all()
        return [r.to_dict() for r in rows]


def bind(open_id: str, user_id: int, chat_id: Optional[str] = None) -> dict:
    """把 open_id 绑定到指定人员，并移出待绑定表。

    - 若该 open_id 已绑到别人，先解绑旧人（open_id 唯一使用）
    - chat_id 传了才覆盖，否则保留原值
    """
    if not open_id:
        raise ValueError("open_id 不能为空")

    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise LookupError(f"人员 {user_id} 不存在")

        for other in s.execute(
            select(User).where(User.feishu_open_id == open_id, User.id != user_id)
        ).scalars().all():
            other.feishu_open_id = ""

        u.feishu_open_id = open_id
        if chat_id:
            u.feishu_chat_id = chat_id

        row = s.get(PendingBinding, open_id)
        if row is not None:
            s.delete(row)

        result = {
            "open_id": open_id,
            "user_id": u.id,
            "name": u.name,
            "feishu_open_id": u.feishu_open_id or "",
            "feishu_chat_id": u.feishu_chat_id or "",
        }
    return result


def dismiss(open_id: str) -> bool:
    """忽略（删除）一条待绑定记录。"""
    if not open_id:
        return False
    with session_scope() as s:
        row = s.get(PendingBinding, open_id)
        if row is None:
            return False
        s.delete(row)
    return True
