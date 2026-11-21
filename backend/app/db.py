"""Database connection and session handling."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import Any, TypeVar

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T")

# Azure SQL serverless pauses when idle. The first connection after a pause is
# refused while the database resumes, which takes up to about a minute.
CONNECT_ATTEMPTS = 6
MAX_BACKOFF_SECONDS = 15


class Base(DeclarativeBase):
    """Parent class for every table in app/models.py."""


def connect_with_retry(
    connect: Callable[[], T],
    retry_on: type[BaseException] | tuple[type[BaseException], ...],
    attempts: int = CONNECT_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call connect(), retrying with growing pauses (2, 4, 8, 15, 15 s) if it fails."""
    for attempt in range(1, attempts + 1):
        try:
            return connect()
        except retry_on as exc:
            if attempt == attempts:
                raise
            wait = min(2**attempt, MAX_BACKOFF_SECONDS)
            log.warning("Database not reachable (attempt %d/%d), retrying in %ds: %s",
                        attempt, attempts, wait, type(exc).__name__)
            sleep(wait)
    raise AssertionError("unreachable")


def _make_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        # SQLite needs this to be used from FastAPI's worker threads.
        return create_engine(url, connect_args={"check_same_thread": False})

    # pool_pre_ping tests each pooled connection before use and replaces dead ones;
    # pool_recycle retires connections before Azure's idle timeout would kill them.
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)

    @event.listens_for(engine, "do_connect")
    def _wait_for_resume(dialect: Any, _record: Any, cargs: Any, cparams: Any) -> Any:
        return connect_with_retry(lambda: dialect.connect(*cargs, **cparams),
                                  retry_on=dialect.loaded_dbapi.Error)

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create any tables that don't exist yet.

    A real system would use migrations (Alembic) so the schema can change
    without losing data. For a demo whose data can be re-seeded at any time,
    creating tables at startup is simpler.
    """
    from app import models  # noqa: F401  (registers the tables on Base)

    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
