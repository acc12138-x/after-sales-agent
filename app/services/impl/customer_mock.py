"""CustomerService 的 Mock 实现。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.base import BaseService
from app.services.registry import register_service


DATA_DIR = Path(__file__).parent.parent / "data"


class CustomerService(BaseService):
    name = "customer"

    def setup(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        f = DATA_DIR / "customers.json"
        if f.exists():
            with open(f, encoding="utf-8") as fp:
                self._data = json.load(fp)
        super().setup()

    def get_customer(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(user_id)

    def is_vip(self, user_id: str) -> bool:
        c = self.get_customer(user_id)
        return bool(c and c.get("vip"))


register_service("customer", CustomerService)
