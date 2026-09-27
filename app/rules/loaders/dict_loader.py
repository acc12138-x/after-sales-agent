"""内存规则加载器：测试 / 动态注入用。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.rules.core.types import Rule
from app.rules.loaders.base import BaseLoader


class DictLoader(BaseLoader):
    def __init__(self, rules: List[Dict[str, Any]]):
        self._rules = rules

    def load(self) -> List[Rule]:
        out = []
        for r in self._rules:
            out.append(Rule(
                id=r.get("id", ""),
                name=r.get("name", ""),
                conditions=r.get("conditions", []),
                result=r.get("result", {}),
                category=r.get("category"),
                group=r.get("group"),
                tags=r.get("tags", []),
                priority=int(r.get("priority", 0)),
                enabled=bool(r.get("enabled", True)),
            ))
        return out
