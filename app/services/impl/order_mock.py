"""OrderService 的 Mock 实现：JSON 文件数据源。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.base import BaseService
from app.services.registry import register_service


DATA_DIR = Path(__file__).parent.parent / "data"


class OrderService(BaseService):
    name = "order"

    def setup(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        f = DATA_DIR / "orders.json"
        if f.exists():
            with open(f, encoding="utf-8") as fp:
                self._data = json.load(fp)
        super().setup()

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(order_id)

    def get_user_orders(self, user_id: str) -> List[Dict[str, Any]]:
        return [o for o in self._data.values() if o.get("user_id") == user_id]

    def days_since_delivered(self, order_id: str) -> Optional[int]:
        o = self.get_order(order_id)
        if not o or not o.get("delivered_at"):
            return None
        delivered = datetime.fromisoformat(o["delivered_at"])
        return (datetime.now() - delivered).days


register_service("order", OrderService)
