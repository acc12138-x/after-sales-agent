"""匹配器：可扩展、可注册。"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

from app.intent.core.types import Intent, IntentContext, IntentMatch


class BaseMatcher(ABC):
    """匹配器基类。

    子类实现 `score(intent, ctx) -> (score, matched_value)`。
    返回 (0, "") 表示不命中。
    """

    name: str = "base"

    @abstractmethod
    def score(self, intent: Intent, ctx: IntentContext) -> tuple[float, str]:
        raise NotImplementedError


class KeywordMatcher(BaseMatcher):
    """关键词匹配：每个命中 +10 分，命中越多分越高（封顶 30）。"""

    name = "keyword"

    def score(self, intent: Intent, ctx: IntentContext) -> tuple[float, str]:
        if not intent.keywords:
            return 0.0, ""
        text = ctx.text or ""
        matched: List[str] = []
        for kw in intent.keywords:
            if kw and kw in text:
                matched.append(kw)
        if not matched:
            return 0.0, ""
        s = min(len(matched) * 10.0, 30.0)
        return s, "/".join(matched[:3])


class RegexMatcher(BaseMatcher):
    """正则匹配：每条命中 +15 分（封顶 30）。"""

    name = "regex"

    def score(self, intent: Intent, ctx: IntentContext) -> tuple[float, str]:
        if not intent.patterns:
            return 0.0, ""
        text = ctx.text or ""
        matched: List[str] = []
        for p in intent.patterns:
            try:
                if re.search(p, text, re.IGNORECASE):
                    matched.append(p)
            except re.error:
                continue
        if not matched:
            return 0.0, ""
        s = min(len(matched) * 15.0, 30.0)
        return s, matched[0]


class KeywordAndRegexMatcher(BaseMatcher):
    """组合匹配器：加权求和 + 优先级加成。"""

    name = "combo"

    def __init__(self, km: KeywordMatcher | None = None, rm: RegexMatcher | None = None):
        self.km = km or KeywordMatcher()
        self.rm = rm or RegexMatcher()

    def score(self, intent: Intent, ctx: IntentContext) -> tuple[float, str]:
        ks, kv = self.km.score(intent, ctx)
        rs, rv = self.rm.score(intent, ctx)
        total = ks + rs
        if total <= 0:
            return 0.0, ""
        # priority 加成：每 100 分 = +1
        total += intent.priority / 100.0
        matched_by = []
        if kv:
            matched_by.append(f"kw:{kv}")
        if rv:
            matched_by.append(f"re:{rv}")
        return total, " | ".join(matched_by)


# ---------- 匹配器注册表 ----------
_MATCHER_REGISTRY: Dict[str, Type[BaseMatcher]] = {
    "keyword": KeywordMatcher,
    "regex": RegexMatcher,
    "combo": KeywordAndRegexMatcher,
}


def register_matcher(name: str, cls: Type[BaseMatcher], override: bool = False) -> None:
    if not override and name in _MATCHER_REGISTRY:
        raise ValueError(f"匹配器已存在: {name}")
    _MATCHER_REGISTRY[name] = cls


def get_matcher(name: str) -> Optional[BaseMatcher]:
    cls = _MATCHER_REGISTRY.get(name)
    return cls() if cls else None


def list_matchers() -> list[str]:
    return sorted(_MATCHER_REGISTRY.keys())
