from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _is_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite")


@lru_cache(maxsize=4)
def get_engine(database_url: str | None = None) -> Engine:
    resolved_database_url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if _is_sqlite(resolved_database_url) else {}
    return create_engine(
        resolved_database_url,
        connect_args=connect_args,
        future=True,
    )


@lru_cache(maxsize=4)
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_db_state() -> None:
    get_session_factory.cache_clear()
    get_engine.cache_clear()
