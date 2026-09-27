"""操作符注册表：内置常用操作符，支持业务自定义。"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict


OperatorFn = Callable[[Any, Any], bool]

_REGISTRY: Dict[str, OperatorFn] = {}


def register_operator(name: str, fn: OperatorFn, override: bool = False) -> None:
    """注册操作符。

    - name:     操作符名（YAML 里写的 op 字段）
    - fn:       (actual, expected) -> bool
    - override: 是否覆盖同名操作符
    """
    if not override and name in _REGISTRY:
        raise ValueError(f"操作符已存在: {name}")
    _REGISTRY[name] = fn


def get_operator(name: str) -> OperatorFn | None:
    return _REGISTRY.get(name)


def list_operators() -> list[str]:
    return sorted(_REGISTRY.keys())


# ---------- 内置操作符 ----------
def _safe_cmp(a, b, op):
    try:
        return op(a, b)
    except (TypeError, ValueError):
        return False


def _builtin_eq(a, b): return _safe_cmp(a, b, lambda x, y: x == y)
def _builtin_ne(a, b): return _safe_cmp(a, b, lambda x, y: x != y)
def _builtin_lt(a, b): return _safe_cmp(a, b, lambda x, y: x < y)
def _builtin_le(a, b): return _safe_cmp(a, b, lambda x, y: x <= y)
def _builtin_gt(a, b): return _safe_cmp(a, b, lambda x, y: x > y)
def _builtin_ge(a, b): return _safe_cmp(a, b, lambda x, y: x >= y)
def _builtin_in(a, b): return _safe_cmp(a, b, lambda x, y: x in (y or []))
def _builtin_not_in(a, b): return _safe_cmp(a, b, lambda x, y: x not in (y or []))
def _builtin_contains(a, b): return _safe_cmp(a, b, lambda x, y: y in x)
def _builtin_regex(a, b):
    try:
        return re.search(str(b), str(a)) is not None
    except Exception:
        return False
def _builtin_exists(a, _): return a is not None
def _builtin_not_exists(a, _): return a is None
def _builtin_between(a, b):
    try:
        lo, hi = b
        return lo <= a <= hi
    except Exception:
        return False


BUILTIN_OPERATORS = {
    "eq": _builtin_eq,
    "ne": _builtin_ne,
    "lt": _builtin_lt,
    "le": _builtin_le,
    "gt": _builtin_gt,
    "ge": _builtin_ge,
    "in": _builtin_in,
    "not_in": _builtin_not_in,
    "contains": _builtin_contains,
    "regex": _builtin_regex,
    "exists": _builtin_exists,
    "not_exists": _builtin_not_exists,
    "between": _builtin_between,

    # 别名（兼容 YAML 里写 == / != / <= 等符号形式）
    "==": _builtin_eq,
    "!=": _builtin_ne,
    "<":  _builtin_lt,
    "<=": _builtin_le,
    ">":  _builtin_gt,
    ">=": _builtin_ge,
}


for _name, _fn in BUILTIN_OPERATORS.items():
    _REGISTRY[_name] = _fn
