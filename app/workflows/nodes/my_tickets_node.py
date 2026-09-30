"""查我的工单节点：通过 sender_open_id 反查用户，返回该用户工单。"""
from __future__ import annotations
from typing import List, Optional

from sqlalchemy import select

from app.db.models.ticket import Ticket
from app.db.models.user import User
from app.db.session import session_scope
from app.workflows.state import AgentState


def _find_user_by_feishu(sender_id: str, chat_id: str) -> Optional[dict]:
    """用 open_id 或 chat_id 找用户。"""
    if not sender_id and not chat_id:
        return None
    with session_scope() as s:
        if sender_id:
            u = s.execute(select(User).where(User.feishu_open_id == sender_id)).scalar_one_or_none()
            if u:
                return u.to_dict()
        if chat_id:
            u = s.execute(select(User).where(User.feishu_chat_id == chat_id)).scalar_one_or_none()
            if u:
                return u.to_dict()
    return None


def _find_tickets_by_user(user: dict) -> List[dict]:
    """查该用户名下工单。"""
    with session_scope() as s:
        # 优先用 contact 含手机号
        phone = user.get("phone", "")
        if phone:
            rows = s.execute(
                select(Ticket).where(Ticket.contact.like(f"%{phone}%"))
                .order_by(Ticket.created_at.desc()).limit(10)
            ).scalars().all()
            if rows:
                return [t.to_dict() for t in rows]
        # 退回 assigned_to 匹配
        rows = s.execute(
            select(Ticket).where(Ticket.assigned_to == user.get("name", ""))
            .order_by(Ticket.created_at.desc()).limit(10)
        ).scalars().all()
        return [t.to_dict() for t in rows]


STATUS_CN = {
    "pending": "⏳ 待处理", "assigned": "📋 待接单", "accepted": "✅ 已接单",
    "in_progress": "🔧 处理中", "resolved": "🎯 已解决", "closed": "🔒 已关闭",
    "rejected": "❌ 已拒单", "cancelled": "🚫 已取消",
}


def my_tickets_node(state: AgentState) -> AgentState:
    sender_id = state.get("sender_open_id", "") or ""
    # 从 slots 里也找 chat_id（防主流程没传）
    slots = state.get("slots", {}) or {}
    chat_id = slots.get("_chat_id", "") or ""

    user = _find_user_by_feishu(sender_id, chat_id)
    if not user:
        answer = (
            f"未找到您的账号绑定。\n\n"
            f"您的 open_id：{sender_id or '(未识别)'}\n\n"
            f"已登记到「人员管理 → 待绑定飞书账号」，请管理员一键绑定到您的账户。"
        )
    else:
        tickets = _find_tickets_by_user(user)
        if not tickets:
            answer = f"👤 {user['name']}，您当前没有工单。"
        else:
            lines = [f"👤 **{user['name']}** 的工单（共 {len(tickets)} 个）", ""]
            for t in tickets[:8]:
                st = STATUS_CN.get(t["status"], t["status"])
                dev = t.get("device_model") or "待补"
                err = t.get("error_code") or "待补"
                lines.append(f"- `{t['ticket_id']}` {st}  设备:{dev}  故障码:{err}")
            answer = "\n".join(lines)

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]
    return {
        **state,
        "answer": answer,
        "messages": messages,
        "flow_status": "succeeded",
    }
