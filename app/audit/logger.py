"""审计日志工具（写 MySQL）。"""
from __future__ import annotations
import json
from typing import Optional

from app.db.models.audit_log import AuditLog
from app.db.session import session_scope


def log(
    action: str,
    actor: str = "system",
    target_type: str = "",
    target_id: str = "",
    detail: Optional[dict] = None,
    result: str = "ok",
) -> None:
    """记录审计日志。失败不阻塞主流程。"""
    try:
        with session_scope() as s:
            s.add(AuditLog(
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=json.dumps(detail or {}, ensure_ascii=False),
                result=result,
            ))
    except Exception:
        pass
