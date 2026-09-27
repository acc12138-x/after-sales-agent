"""内置实现集合。导入即注册。"""
from app.services.impl import order_mock, logistics_mock, product_mock, customer_mock

__all__ = ["order_mock", "logistics_mock", "product_mock", "customer_mock"]
