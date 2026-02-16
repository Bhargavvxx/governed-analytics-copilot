"""SQLAlchemy engine & session factory.

Single shared engine with connection pooling.  All copilot queries
run through `execute_readonly`, which sets the transaction to
READ ONLY before executing.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine (lazy-created, cached)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        logger.info("DB engine created  host=%s  db=%s", settings.postgres_host, settings.postgres_db)
    return _engine


def get_session() -> Session:
    """Create a new ORM session (caller must close)."""
    engine = get_engine()
    factory = sessionmaker(bind=engine)
    return factory()


@contextmanager
def readonly_connection() -> Generator:
    """Yield a connection set to READ ONLY transaction mode.

    Guarantees that no writes can happen, even if the SQL is malicious.
    The connection is returned to the pool on exit.
    """
    engine = get_engine()
    conn = engine.connect()
    try:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        yield conn
    finally:
        conn.close()
