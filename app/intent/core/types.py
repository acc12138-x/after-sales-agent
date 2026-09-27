"""通用数据结构：Intent / IntentMatch / IntentContext。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Intent:
    id: str
    name: str
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    category: Optional[str] = None
    priority: int = 0
    slots: List[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentMatch:
    intent: Intent
    score: float = 0.0
    matched_by: str = ""            # "keyword" / "regex" / "llm"
    matched_value: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.intent.id

    @property
    def name(self) -> str:
        return self.intent.name


@dataclass
class IntentContext:
    """传给匹配器的上下文（可选）。"""
    text: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    user: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
