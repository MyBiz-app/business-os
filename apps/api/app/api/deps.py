from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import EngineDep, open_session, session_scope, set_tenant

UserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_session(user: UserDep, engine: EngineDep) -> Iterator[Session]:
    """A session scoped to the signed-in user (no tenant selected)."""
    yield from session_scope(open_session(engine, user.id))


SessionDep = Annotated[Session, Depends(get_session)]


def get_tenant_session(
    session: SessionDep, tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")]
) -> Session:
    """A session scoped to one tenant. Fails unless the user is a member of that tenant."""
    set_tenant(session, tenant_id)
    if session.execute(text("SELECT app.current_tenant_id()")).scalar() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_a_member")
    return session


TenantSessionDep = Annotated[Session, Depends(get_tenant_session)]
