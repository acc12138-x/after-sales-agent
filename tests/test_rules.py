"""规则引擎测试。"""
from app.rules.core.engine import RuleEngine
from app.rules.core.operators import get_operator, list_operators
from app.rules.core.types import MatchOptions, Rule


class TestOperators:
    def test_eq(self):
        op = get_operator("eq")
        assert op(1, 1) is True
        assert op(1, 2) is False

    def test_le(self):
        op = get_operator("le")
        assert op(5, 10) is True
        assert op(10, 5) is False

    def test_in(self):
        op = get_operator("in")
        assert op("a", ["a", "b"]) is True
        assert op("c", ["a", "b"]) is False

    def test_builtin_operators_present(self):
        ops = list_operators()
        for name in ["eq", "ne", "lt", "le", "gt", "ge", "in", "not_in", "contains", "between"]:
            assert name in ops


class TestRuleEngine:
    def test_basic_match(self):
        e = RuleEngine()
        e.add_rule(Rule(
            id="r1", name="test",
            conditions=[{"field": "age", "op": "ge", "value": 18}],
            result={"ok": True},
        ))
        m = e.match({"age": 20}, MatchOptions(stop_on_first=True))
        assert len(m) == 1
        assert m[0].id == "r1"

    def test_no_match(self):
        e = RuleEngine()
        e.add_rule(Rule(
            id="r1", name="test",
            conditions=[{"field": "age", "op": "ge", "value": 18}],
            result={"ok": True},
        ))
        m = e.match({"age": 10}, MatchOptions(stop_on_first=True))
        assert len(m) == 0

    def test_priority_order(self):
        e = RuleEngine()
        e.add_rule(Rule(id="low", name="low", priority=10,
                        conditions=[{"field": "n", "op": "gt", "value": 0}],
                        result={"hit": "low"}))
        e.add_rule(Rule(id="high", name="high", priority=100,
                        conditions=[{"field": "n", "op": "gt", "value": 0}],
                        result={"hit": "high"}))
        m = e.match({"n": 5}, MatchOptions(stop_on_first=True))
        assert m[0].id == "high"
