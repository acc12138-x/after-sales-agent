"""YAML 意图加载器。

格式：
    intents:
      - id: return
        name: 退货
        parent: after_sales
        keywords: ["退货", "想退"]
        patterns: ["^我要退"]
        priority: 100
        slots: [order_id, reason]
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from app.intent.core.types import Intent


class YamlIntentLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> List[Intent]:
        if self.path.is_dir():
            intents: List[Intent] = []
            for f in sorted(self.path.glob("*.yaml")):
                intents.extend(self._load_file(f))
            for f in sorted(self.path.glob("*.yml")):
                intents.extend(self._load_file(f))
            return intents
        return self._load_file(self.path)

    def _load_file(self, f: Path) -> List[Intent]:
        with open(f, encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        raw = data.get("intents", [])
        out: List[Intent] = []
        for r in raw:
            out.append(Intent(
                id=r.get("id", ""),
                name=r.get("name", ""),
                keywords=r.get("keywords", []),
                patterns=r.get("patterns", []),
                parent=r.get("parent"),
                category=r.get("category"),
                priority=int(r.get("priority", 0)),
                slots=r.get("slots", []),
                description=r.get("description", ""),
                enabled=bool(r.get("enabled", True)),
                metadata={"_source_file": f.name},
            ))
        return out
