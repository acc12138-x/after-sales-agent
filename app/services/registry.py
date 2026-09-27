"""服务注册中心：惰性初始化、按名获取。"""
from __future__ import annotations

import threading
from typing import Any, Dict, Type

from app.services.base import BaseService


class ServiceRegistry:
    _lock = threading.Lock()
    _classes: Dict[str, Type[BaseService]] = {}
    _instances: Dict[str, BaseService] = {}
    _configs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        service_cls: Type[BaseService],
        config: Dict[str, Any] | None = None,
        override: bool = False,
    ) -> None:
        with cls._lock:
            if not override and name in cls._classes:
                raise ValueError(f"服务已注册: {name}")
            cls._classes[name] = service_cls
            cls._configs[name] = config or {}
            cls._instances.pop(name, None)

    @classmethod
    def get(cls, name: str) -> BaseService:
        with cls._lock:
            if name in cls._instances:
                return cls._instances[name]
            if name not in cls._classes:
                raise KeyError(f"服务未注册: {name}（已注册: {list(cls._classes.keys())}）")
            inst = cls._classes[name](cls._configs[name])
            inst.setup()
            cls._instances[name] = inst
            return inst

    @classmethod
    def list_services(cls) -> list[str]:
        return sorted(cls._classes.keys())

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instances.clear()


def register_service(name, cls, config=None, override=False):
    ServiceRegistry.register(name, cls, config, override)


def get_service(name: str) -> BaseService:
    return ServiceRegistry.get(name)


def list_services() -> list[str]:
    return ServiceRegistry.list_services()
