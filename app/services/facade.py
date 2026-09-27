"""统一门面：把所有业务服务聚合为一个对象。"""
from __future__ import annotations

# 关键：import impl 包触发所有 register_service()
import app.services.impl  # noqa: F401

from app.services.registry import get_service


class BusinessServices:
    @property
    def order(self):
        return get_service("order")

    @property
    def logistics(self):
        return get_service("logistics")

    @property
    def product(self):
        return get_service("product")

    @property
    def customer(self):
        return get_service("customer")


_facade: BusinessServices | None = None


def get_services() -> BusinessServices:
    global _facade
    if _facade is None:
        _facade = BusinessServices()
    return _facade
