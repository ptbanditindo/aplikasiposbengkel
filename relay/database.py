"""Engine dan sesi relay terpisah dari engine aplikasi lokal."""
from __future__ import annotations

from typing import Generator, Optional

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database.session import build_engine

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def init_engine(url: Optional[str] = None) -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = build_engine(url or settings.relay_database_url)
        _session_factory = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _engine


def get_engine() -> Engine:
    return _engine or init_engine()


def session_factory() -> sessionmaker:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


def get_relay_db() -> Generator[Session, None, None]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def reset_engine_for_tests() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
