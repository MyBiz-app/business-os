"""Database access.

Every transaction runs as the `app_api` role, with the current user and tenant set as
transaction-local settings that row-level security reads. The context is re-applied at the
start of each transaction, so a commit can never leave a session running unrestricted."""

import logging
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import get_settings
from app.core.logging import log

USER_KEY = "app.user_id"
TENANT_KEY = "app.tenant_id"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        connect_args={} if settings.db_prepared_statements else {"prepare_threshold": None},
    )
    log_slow_queries(engine, settings.slow_query_ms)
    return engine


def log_slow_queries(engine: Engine, threshold_ms: int) -> None:
    """Log statements slower than the threshold: the statement text only, never its parameters
    (they hold personal data)."""
    if threshold_ms <= 0:
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _start(conn, _cursor, _statement, _parameters, _context, _executemany) -> None:
        conn.info["query_started"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _finish(conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        elapsed_ms = (
            time.perf_counter() - conn.info.pop("query_started", time.perf_counter())
        ) * 1000
        if elapsed_ms >= threshold_ms:
            log(
                logging.WARNING,
                "slow query",
                duration_ms=round(elapsed_ms, 1),
                statement=" ".join(statement.split())[:300],
            )


def _apply_context(connection: Connection, user_id: str, tenant_id: str) -> None:
    connection.execute(text("SET LOCAL ROLE app_api"))
    connection.execute(
        text(
            "SELECT set_config('app.user_id', :uid, true), set_config('app.tenant_id', :tid, true)"
        ),
        {"uid": user_id, "tid": tenant_id},
    )


class RequestSession(Session):
    """A session bound to one user and, optionally, one tenant."""


@event.listens_for(RequestSession, "after_begin")
def _on_begin(session: Session, _transaction: SessionTransaction, connection: Connection) -> None:
    _apply_context(connection, session.info.get(USER_KEY, ""), session.info.get(TENANT_KEY, ""))


def open_session(engine: Engine, user_id: UUID | None, tenant_id: UUID | None = None) -> Session:
    session = RequestSession(engine)
    session.info[USER_KEY] = str(user_id or "")
    session.info[TENANT_KEY] = str(tenant_id or "")
    return session


def set_tenant(session: Session, tenant_id: UUID) -> None:
    session.info[TENANT_KEY] = str(tenant_id)
    session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})


def session_scope(session: Session) -> Iterator[Session]:
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


EngineDep = Annotated[Engine, Depends(get_engine)]
