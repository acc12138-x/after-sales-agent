"""查询工程师节点：支持查工程师信息 + 查某工程师的工单。"""
from __future__ import annotations
import re
from typing import List, Optional

from sqlalchemy import select

from app.db.models.user import User
from app.db.models.ticket import Ticket
from app.db.session import session_scope
from app.workflows.state import AgentState


NAME_PAT = re.compile(r"([赵张李王孙周吴郑陈刘杨黄胡]工)")


def _extract_name(text: str) -> Optional[str]:
    m = NAME_PAT.search(text)
    return m.group(1) if m else None


def _wants_tickets(text: str) -> bool:
    return "工单" in text or "单子" in text or "任务" in text


def _wants_available(text: str) -> bool:
    return any(k in text for k in ["有空", "空闲", "谁在", "哪个工程", "谁有"])


def _list_available() -> List[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(User).where(User.role == "engineer", User.status == "online").order_by(User.current_load)
        ).scalars().all()
        return [e.to_dict() for e in rows]


def _find_by_name(name: str) -> Optional[dict]:
    with session_scope() as s:
        e = s.execute(select(User).where(User.role == "engineer", User.name == name)).scalar_one_or_none()
        return e.to_dict() if e else None


def _find_engineer_tickets(name: str) -> List[dict]:
    """查该工程师负责的工单。"""
    with session_scope() as s:
        rows = s.execute(
            select(Ticket).where(Ticket.assigned_to == name)
            .order_by(Ticket.created_at.desc()).limit(20)
        ).scalars().all()
        return [t.to_dict() for t in rows]


STATUS_CN = {
    "pending": "⏳ 待处理", "assigned": "📋 待接单", "accepted": "✅ 已接单",
    "in_progress": "🔧 处理中", "resolved": "🎯 已解决", "closed": "🔒 已关闭",
    "rejected": "❌ 已拒单", "cancelled": "🚫 已取消",
}


def engineer_query_node(state: AgentState) -> AgentState:
    text = state.get("user_input", "")
    name = _extract_name(text)

    # 情况 1：指名人 + 查工单
    if name and _wants_tickets(text):
        e = _find_by_name(name)
        if not e:
            answer = f"未找到工程师 **{name}**。"
        else:
            tickets = _find_engineer_tickets(name)
            if not tickets:
                answer = f"👷 **{name}** 当前没有工单。"
            else:
                lines = [f"👷 **{name}** 的工单（共 {len(tickets)} 个）：", ""]
                for t in tickets[:10]:
                    st = STATUS_CN.get(t.get("status"), t.get("status"))
                    lines.append(
                        f"- `{t['ticket_id']}` [{t.get('ticket_type') or 'repair'}] "
                        f"{st}  设备：{t.get('device_model') or '待补'}"
                    )
                answer = "\n".join(lines)

    # 情况 2：指名人 + 查空闲/信息
    elif name:
        e = _find_by_name(name)
        if not e:
            answer = f"未找到工程师 **{name}**。"
        else:
            status = "🟢 在线" if e["status"] == "online" else "⚪ 离线"
            load = e["current_load"]
            max_load = e["max_load"]
            if e["status"] != "online":
                verdict = "（离线，不接单）"
            elif load >= max_load:
                verdict = "（🔴 已满，暂不接新单）"
            elif load >= max_load * 0.7:
                verdict = "（🟠 较忙）"
            else:
                verdict = "（✅ 有空，可接单）"

            skills = "、".join(e["skills"]) if e["skills"] else "-"
            answer = (
                f"👷 **{name}** {status} {verdict}\n"
                f"- 区域：{e['region'] or '-'}\n"
                f"- 技能：{skills}\n"
                f"- 负载：{load} / {max_load}\n"
                f"- 手机：{e['phone'] or '-'}"
            )

    # 情况 3：问"谁有空"
    elif _wants_available(text):
        avail = _list_available()
        if not avail:
            answer = "暂无在线工程师。"
        else:
            lines = ["👷 **当前在线工程师**（按负载排序）：", ""]
            for e in avail[:8]:
                if e["current_load"] >= e["max_load"]:
                    icon = "🔴"
                elif e["current_load"] >= e["max_load"] * 0.7:
                    icon = "🟠"
                else:
                    icon = "🟢"
                lines.append(
                    f"- {icon} **{e['name']}**（{e['region'] or '-'}）"
                    f"  负载 {e['current_load']}/{e['max_load']}"
                    f"  技能：{'、'.join(e['skills'][:3]) or '-'}"
                )
            answer = "\n".join(lines)

    # 情况 4：只提到"工程师"两个字
    else:
        avail = _list_available()
        lines = [f"👷 当前有 **{len(avail)}** 位在线工程师", ""]
        for e in avail[:5]:
            lines.append(f"- {e['name']}（{e['region'] or '-'}）{e['current_load']}/{e['max_load']}")
        answer = "\n".join(lines)

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]
    return {
        **state,
        "answer": answer,
        "messages": messages,
        "flow_status": "succeeded",
    }
