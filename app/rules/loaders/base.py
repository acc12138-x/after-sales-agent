"""加载器基类：定义接口，业务可自定义实现。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.rules.core.types import Rule


class BaseLoader(ABC):
    @abstractmethod
    def load(self) -> List[Rule]:
        """返回 Rule 列表。"""
        raise NotImplementedError
