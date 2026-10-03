from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import EngineDep, open_session, session_scope, set_tenant
from app.permissions import Permission, role_allows

UserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_session(user: UserDep, engine: EngineDep) -> Iterator[Session]:
    """A session scoped to the signed-in user (no tenant selected)."""
    yield from session_scope(open_session(engine, user.id))


SessionDep = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class TenantContext:
    session: Session
    tenant_id: UUID
    role: str


def get_tenant_context(
    session: SessionDep, tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")]
) -> TenantContext:
    """Scopes the session to one tenant. Fails unless the user is a member of that tenant."""
    set_tenant(session, tenant_id)
    role = session.execute(
        text("""
            SELECT role FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
        """)
    ).scalar()
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_a_member")
    return TenantContext(session=session, tenant_id=tenant_id, role=role)


TenantDep = Annotated[TenantContext, Depends(get_tenant_context)]


def require(permission: Permission) -> Callable[[TenantContext], TenantContext]:
    """Dependency that also checks the member's role grants `permission`."""

    def check(context: TenantDep) -> TenantContext:
        if not role_allows(context.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return context

    return check
