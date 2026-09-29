"""数据库连接与会话管理。"""
from __future__ import annotations
import os

from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        db_mode = (getattr(s, "db_mode", "") or "mysql").lower()
        if db_mode == "sqlite":
            url = "sqlite:///./data/app.db"
        else:
            url = (
                f"mysql+pymysql://{s.mysql_user}:{s.mysql_password}"
                f"@{s.mysql_host}:{s.mysql_port}/{s.mysql_database}?charset=utf8"
            )
        if db_mode == "sqlite":
            _engine = create_engine(url, echo=False)
        else:
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10,
                echo=False,
            )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_session() -> Session:
    return get_session_factory()()


@contextmanager
def session_scope():
    """上下文管理器：自动 commit/rollback/close。"""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """配置变更后重置引擎（供 admin/reload 调用）。"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db() -> None:
    """创建所有表（首次运行或测试用）。"""
    from app.db.base import Base
    import app.db.models  # 触发模型注册
    Base.metadata.create_all(bind=get_engine())
