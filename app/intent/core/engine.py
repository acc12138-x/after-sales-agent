"""意图识别引擎：与业务无关。"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional

from app.intent.core.matchers import BaseMatcher, KeywordAndRegexMatcher
from app.intent.core.types import Intent, IntentContext, IntentMatch


LLMFn = Callable[[str, List[Intent]], Optional[tuple[str, float]]]


class IntentEngine:
    """通用意图识别引擎。

    用法:
        engine = IntentEngine()
        engine.add_intents(intents)
        matches = engine.classify("我要退货")
        top = engine.classify_top("我要退货")
    """

    def __init__(self, matcher: Optional[BaseMatcher] = None):
        self._intents: List[Intent] = []
        self._matcher: BaseMatcher = matcher or KeywordAndRegexMatcher()
        self._llm_fn: Optional[LLMFn] = None
        self._llm_threshold: float = 5.0    # 规则得分低于此值时启用 LLM 兜底

    # ---------- 意图管理 ----------
    def add_intent(self, intent: Intent) -> None:
        self._intents.append(intent)

    def add_intents(self, intents: Iterable[Intent]) -> None:
        self._intents.extend(intents)

    def remove_intent(self, intent_id: str) -> int:
        before = len(self._intents)
        self._intents = [i for i in self._intents if i.id != intent_id]
        return before - len(self._intents)

    def clear(self) -> None:
        self._intents = []

    @property
    def intents(self) -> List[Intent]:
        return list(self._intents)

    @property
    def size(self) -> int:
        return len(self._intents)

    # ---------- 匹配器 / LLM ----------
    def set_matcher(self, matcher: BaseMatcher) -> None:
        self._matcher = matcher

    def set_llm_fn(self, fn: Optional[LLMFn], threshold: float = 5.0) -> None:
        self._llm_fn = fn
        self._llm_threshold = threshold

    # ---------- 识别 ----------
    def classify(
        self,
        text: str,
        context: Optional[IntentContext] = None,
        top_k: Optional[int] = None,
    ) -> List[IntentMatch]:
        ctx = context or IntentContext(text=text)
        if not ctx.text:
            ctx.text = text

        results: List[IntentMatch] = []
        for intent in self._intents:
            if not intent.enabled:
                continue
            score, matched = self._matcher.score(intent, ctx)
            if score > 0:
                results.append(IntentMatch(
                    intent=intent,
                    score=score,
                    matched_by=self._matcher.name,
                    matched_value=matched,
                ))

        # LLM 兜底
        if self._llm_fn and (not results or max(r.score for r in results) < self._llm_threshold):
            try:
                llm_result = self._llm_fn(text, self._intents)
                if llm_result:
                    intent_id, conf = llm_result
                    target = next((i for i in self._intents if i.id == intent_id), None)
                    if target:
                        # 若已存在，替换/提升
                        existing = next((r for r in results if r.id == intent_id), None)
                        if existing:
                            existing.score += conf * 100
                            existing.matched_by = "llm"
                        else:
                            results.append(IntentMatch(
                                intent=target,
                                score=conf * 100,
                                matched_by="llm",
                                matched_value=f"llm:{intent_id}",
                            ))
            except Exception:
                pass

        results.sort(key=lambda r: (-r.score, -r.intent.priority))
        if top_k:
            results = results[:top_k]
        return results

    def classify_top(self, text: str, context: Optional[IntentContext] = None) -> Optional[IntentMatch]:
        rs = self.classify(text, context, top_k=1)
        return rs[0] if rs else None

    def get_intent(self, intent_id: str) -> Optional[Intent]:
        return next((i for i in self._intents if i.id == intent_id), None)

    def get_children(self, parent_id: str) -> List[Intent]:
        return [i for i in self._intents if i.parent == parent_id]
