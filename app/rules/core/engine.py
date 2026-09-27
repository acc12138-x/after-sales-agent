"""通用规则引擎：与业务无关。"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.rules.core.conditions import eval_all_conditions
from app.rules.core.types import MatchOptions, Rule, RuleMatch


class RuleEngine:
    """通用规则引擎。

    用法：
        engine = RuleEngine()
        engine.add_rules(rules)
        matches = engine.match(context, MatchOptions(category="return", stop_on_first=True))
    """

    def __init__(self, rules: Optional[Iterable[Rule]] = None):
        self._rules: List[Rule] = list(rules) if rules else []

    # ---------- 规则管理 ----------
    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_rules(self, rules: Iterable[Rule]) -> None:
        self._rules.extend(rules)

    def remove_rule(self, rule_id: str) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return before - len(self._rules)

    def clear(self) -> None:
        self._rules = []

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules)

    @property
    def size(self) -> int:
        return len(self._rules)

    # ---------- 匹配 ----------
    def match(
        self,
        context: Dict[str, Any],
        options: Optional[MatchOptions] = None,
    ) -> List[RuleMatch]:
        opts = options or MatchOptions()
        candidates = self._filter(opts)
        candidates.sort(key=lambda r: -r.priority)

        results: List[RuleMatch] = []
        for r in candidates:
            if eval_all_conditions(r.conditions, context):
                results.append(RuleMatch(
                    rule=r,
                    conditions_snapshot=list(r.conditions),
                ))
                if opts.stop_on_first:
                    break
                if opts.limit and len(results) >= opts.limit:
                    break

        # 无命中且指定了 default
        if not results and opts.default is not None:
            results.append(RuleMatch(rule=opts.default, conditions_snapshot=[]))
        return results

    def _filter(self, opts: MatchOptions) -> List[Rule]:
        out = []
        for r in self._rules:
            if not opts.include_disabled and not r.enabled:
                continue
            if opts.category is not None and r.category != opts.category:
                continue
            if opts.group is not None and r.group != opts.group:
                continue
            if opts.tags and not set(opts.tags) & set(r.tags):
                continue
            out.append(r)
        return out
