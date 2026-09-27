"""统一门面：把所有业务服务聚合为一个对象。"""
from __future__ import annotations

from app.services.registry import get_service


class BusinessServices:
    """业务服务聚合门面。

    用法:
        svc = BusinessServices()
        order = svc.order.get_order("O20260101001")
        vip = svc.customer.is_vip("U1001")
    """

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
