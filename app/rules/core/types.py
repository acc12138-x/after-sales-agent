"""通用数据结构：Rule / RuleMatch / Context。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Rule:
    """一条规则。

    - conditions: 条件列表，全部满足才算命中
    - result:     任意 dict，由业务侧解析
    - priority:   数值越大优先级越高
    """
    id: str
    name: str
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)
    category: Optional[str] = None
    group: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleMatch:
    """一条命中结果。"""
    rule: Rule
    conditions_snapshot: List[Dict[str, Any]] = field(default_factory=list)

    # 便捷访问
    @property
    def id(self) -> str:
        return self.rule.id

    @property
    def name(self) -> str:
        return self.rule.name

    @property
    def result(self) -> Dict[str, Any]:
        return self.rule.result

    @property
    def priority(self) -> int:
        return self.rule.priority


@dataclass
class MatchOptions:
    """匹配选项。"""
    category: Optional[str] = None
    group: Optional[str] = None
    tags: Optional[List[str]] = None          # 任一 tag 命中即可
    stop_on_first: bool = False               # 只取优先级最高一条
    limit: Optional[int] = None               # 最多返回几条
    include_disabled: bool = False
    default: Optional[Rule] = None            # 无命中时的默认规则
