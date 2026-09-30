"""意图引擎单例工厂。"""
from __future__ import annotations

from pathlib import Path

from app.intent.core.engine import IntentEngine
from app.intent.loaders.yaml_loader import YamlIntentLoader


DEFAULT_DATA_DIR = Path(__file__).parent / "data"

_ENGINES: dict = {}


def get_intent_engine(name: str = "default") -> IntentEngine:
    if name not in _ENGINES:
        engine = IntentEngine()
        loader = YamlIntentLoader(DEFAULT_DATA_DIR)
        engine.add_intents(loader.load())
        _ENGINES[name] = engine
    return _ENGINES[name]


def reload_intent_engine(name: str = "default") -> IntentEngine:
    _ENGINES.pop(name, None)
    return get_intent_engine(name)
