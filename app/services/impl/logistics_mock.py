"""LogisticsService 的 Mock 实现。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.base import BaseService
from app.services.registry import register_service


DATA_DIR = Path(__file__).parent.parent / "data"


class LogisticsService(BaseService):
    name = "logistics"

    def setup(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        f = DATA_DIR / "logistics.json"
        if f.exists():
            with open(f, encoding="utf-8") as fp:
                self._data = json.load(fp)
        super().setup()

    def get_tracking(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(order_id)

    def get_eta(self, order_id: str) -> Optional[str]:
        info = self.get_tracking(order_id)
        return info.get("eta") if info else None


register_service("logistics", LogisticsService)
