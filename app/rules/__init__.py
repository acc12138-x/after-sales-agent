"""通用规则引擎框架。

核心设计：
- core/      纯框架，与业务无关
- loaders/   可插拔的规则加载器
- data/      业务规则数据（YAML）
- factory.py 单例工厂
"""
from app.rules.factory import get_engine, get_engine_manager

__all__ = ["get_engine", "get_engine_manager"]
