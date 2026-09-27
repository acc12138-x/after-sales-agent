"""YAML 规则加载器。

YAML 结构：
    group: after_sales          # 可选，全局 group
    rules:
      - id: rule_1
        name: xxx
        category: return
        priority: 100
        conditions:
          - field: days_since_received
            op: le
            value: 7
        result:
          allowed: true
          message: xxx
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.rules.core.types import Rule
from app.rules.loaders.base import BaseLoader


class YamlLoader(BaseLoader):
    def __init__(self, path: str | Path, group: str | None = None):
        self.path = Path(path)
        self.default_group = group

    def load(self) -> List[Rule]:
        if self.path.is_dir():
            rules = []
            for f in sorted(self.path.glob("*.yaml")):
                rules.extend(self._load_file(f))
            for f in sorted(self.path.glob("*.yml")):
                rules.extend(self._load_file(f))
            return rules
        return self._load_file(self.path)

    def _load_file(self, f: Path) -> List[Rule]:
        with open(f, encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        file_group = data.get("group") or self.default_group
        raw_rules: List[Dict[str, Any]] = data.get("rules", [])

        out: List[Rule] = []
        for r in raw_rules:
            out.append(Rule(
                id=r.get("id", ""),
                name=r.get("name", ""),
                conditions=r.get("conditions", []),
                result=r.get("result", {}),
                category=r.get("category"),
                group=r.get("group") or file_group,
                tags=r.get("tags", []),
                priority=int(r.get("priority", 0)),
                enabled=bool(r.get("enabled", True)),
                description=r.get("description", ""),
                metadata={"_source_file": f.name},
            ))
        return out
