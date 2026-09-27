"""条件评估：支持点号路径、多种操作符。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.rules.core.operators import get_operator


def get_path(context: Dict[str, Any], path: str) -> Any:
    """支持 'user.age' / 'order.items[0].price' 形式的路径。"""
    if not path:
        return None
    cur: Any = context
    for part in path.split("."):
        # 支持 items[0] 形式
        if "[" in part and part.endswith("]"):
            name, _, idx = part.partition("[")
            idx = int(idx.rstrip("]"))
            if isinstance(cur, dict) and name:
                cur = cur.get(name)
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        if cur is None:
            return None
    return cur


def eval_condition(cond: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """单个条件评估。

    cond 格式（YAML/JSON 均可）：
      field: days_since_received    # 支持点号路径
      op: le                        # 操作符名（内置: eq/ne/lt/le/gt/ge/in/not_in/contains/regex/exists/not_exists/between）
      value: 7
      negate: false                 # 可选，结果取反
    """
    field = cond.get("field")
    if not field:
        return False

    op_name = cond.get("op", "eq")
    expected = cond.get("value")
    negate = bool(cond.get("negate", False))

    fn = get_operator(op_name)
    if fn is None:
        raise ValueError(f"未注册的操作符: {op_name}")

    actual = get_path(context, field)
    result = bool(fn(actual, expected))
    return (not result) if negate else result


def eval_all_conditions(
    conditions: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> bool:
    """所有条件 AND 关系；空列表视为 True。"""
    if not conditions:
        return True
    for c in conditions:
        if not eval_condition(c, context):
            return False
    return True
