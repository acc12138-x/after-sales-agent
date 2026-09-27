"""业务服务层框架。

设计：
- base.py      抽象基类 BaseService
- registry.py  服务注册中心
- impl/        具体实现（Mock / 真实）
- data/        Mock 数据（JSON）
"""
from app.services.registry import ServiceRegistry, get_service, register_service

__all__ = ["ServiceRegistry", "get_service", "register_service"]
