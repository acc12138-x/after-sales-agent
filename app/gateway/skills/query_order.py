
"""OpenClaw Skill：查询订单。"""
from __future__ import annotations
from typing import Any, Dict

MOCK_ORDERS = {
    "13800138000": {"order_id": "O20260101", "status": "已发货", "eta": "2 天内到达"},
    "13900139000": {"order_id": "O20260102", "status": "待付款", "eta": "-"},
}


def query_order(phone: str) -> Dict[str, Any]:
    info = MOCK_ORDERS.get(phone)
    if not info:
        return {"found": False, "message": "未找到订单，请核对手机号"}
    return {"found": True, **info}


SCHEMA = {
    "name": "query_order",
    "description": "根据手机号查询订单状态",
    "parameters": {
        "type": "object",
        "properties": {"phone": {"type": "string"}},
        "required": ["phone"],
    },
}
