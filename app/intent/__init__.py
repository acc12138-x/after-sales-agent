"""意图识别框架（可复用）。

设计:
- core/     通用引擎 + 匹配器（无业务）
- loaders/  可插拔加载器
- data/     意图定义（YAML，业务可换）
- factory.py 单例工厂
"""
from app.intent.factory import get_intent_engine, reload_intent_engine

__all__ = ["get_intent_engine", "reload_intent_engine"]
