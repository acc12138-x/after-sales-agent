"""单例工厂：全局共享一个引擎实例。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.rules.core.engine import RuleEngine
from app.rules.loaders.yaml_loader import YamlLoader


DEFAULT_DATA_DIR = Path(__file__).parent / "data"

_ENGINES: dict[str, RuleEngine] = {}


def get_engine(name: str = "default") -> RuleEngine:
    """获取指定名字的引擎，不存在则创建。"""
    if name not in _ENGINES:
        engine = RuleEngine()
        loader = YamlLoader(DEFAULT_DATA_DIR)
        engine.add_rules(loader.load())
        _ENGINES[name] = engine
    return _ENGINES[name]


def get_engine_manager() -> dict[str, RuleEngine]:
    return _ENGINES


def reload_engine(name: str = "default") -> RuleEngine:
    """热重载：规则 YAML 改动后调用。"""
    _ENGINES.pop(name, None)
    return get_engine(name)


def reload_all() -> None:
    for name in list(_ENGINES.keys()):
        reload_engine(name)
