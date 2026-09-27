"""ProductService 的 Mock 实现。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.base import BaseService
from app.services.registry import register_service


DATA_DIR = Path(__file__).parent.parent / "data"


class ProductService(BaseService):
    name = "product"

    def setup(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        f = DATA_DIR / "products.json"
        if f.exists():
            with open(f, encoding="utf-8") as fp:
                self._data = json.load(fp)
        super().setup()

    def get_product(self, sku: str) -> Optional[Dict[str, Any]]:
        return self._data.get(sku)

    def get_warranty_days(self, sku: str) -> Optional[int]:
        p = self.get_product(sku)
        return p.get("warranty_days") if p else None

    def is_special_category(self, sku: str) -> bool:
        p = self.get_product(sku)
        if not p:
            return False
        return p.get("category") in {"内衣", "生鲜", "定制商品"}


register_service("product", ProductService)
