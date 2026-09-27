"""BaseService 抽象基类：定义服务生命周期与调用契约。"""
from __future__ import annotations

from abc import ABC
from typing import Any, Dict


class BaseService(ABC):
    """所有业务服务的基类。

    子类需要:
      - 定义 name 类属性（唯一）
      - 实现 __init__(config: dict) 或在 _setup() 里初始化
      - 提供业务方法（建议同时提供 .info() 用于调试）

    生命周期:
      - 创建：ServiceRegistry.register(name, cls, config)
      - 获取：ServiceRegistry.get(name)
      - 初始化：首次获取时惰性调用 setup()
    """

    name: str = "base"

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self._ready = False

    def setup(self) -> None:
        """惰性初始化。子类可覆盖。"""
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def info(self) -> Dict[str, Any]:
        """返回服务元信息，便于监控/调试。"""
        return {
            "name": self.name,
            "ready": self._ready,
            "config_keys": list(self.config.keys()),
        }
