"""Database access.

Every transaction runs as the `app_api` role, with the current user and tenant set as
transaction-local settings that row-level security reads. The context is re-applied at the
start of each transaction, so a commit can never leave a session running unrestricted."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import get_settings

USER_KEY = "app.user_id"
TENANT_KEY = "app.tenant_id"


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


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
