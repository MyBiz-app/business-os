from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import EngineDep, open_session, session_scope, set_tenant
from app.permissions import Permission, effective_permissions

UserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_session(user: UserDep, engine: EngineDep) -> Iterator[Session]:
    """A session scoped to the signed-in user (no tenant selected)."""
    yield from session_scope(open_session(engine, user.id))


SessionDep = Annotated[Session, Depends(get_session)]


def get_anonymous_session(engine: EngineDep) -> Iterator[Session]:
    """A session for public endpoints: no user, no tenant; RLS hides all tenant data."""
    yield from session_scope(open_session(engine, None))


AnonymousSessionDep = Annotated[Session, Depends(get_anonymous_session)]


@dataclass(frozen=True)
class TenantContext:
    session: Session
    tenant_id: UUID
    role: str
    # Effective permissions: the custom role's switches, or the system role's bundle.
    permissions: frozenset[str] = frozenset()


def get_tenant_context(
    session: SessionDep, tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")]
) -> TenantContext:
    """Scopes the session to one tenant. Fails unless the user is a member of that tenant."""
    set_tenant(session, tenant_id)
    member = session.execute(
        text("""
            SELECT m.role, r.permissions AS custom_permissions
            FROM app.tenant_members m
            LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
            WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = app.current_user_id()
        """)
    ).first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_a_member")
    return TenantContext(
        session=session,
        tenant_id=tenant_id,
        role=member.role,
        permissions=effective_permissions(member.role, member.custom_permissions),
    )


TenantDep = Annotated[TenantContext, Depends(get_tenant_context)]


def has_module(session: Session, *keys: str) -> bool:
    """Whether the current business has any of the modules (works for staff and clients)."""
    return bool(
        session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM app.tenant_modules
                    WHERE tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                      AND module_key = ANY(:keys)
                )
            """),
            {"keys": list(keys)},
        ).scalar_one()
    )


def require(permission: Permission) -> Callable[[TenantContext], TenantContext]:
    """Dependency that also checks the member's role grants `permission`."""

    def check(context: TenantDep) -> TenantContext:
        if permission not in context.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return context

    return check


@dataclass(frozen=True)
class ClientContext:
    session: Session
    tenant_id: UUID
    client_id: UUID


def get_client_context(
    session: SessionDep, tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")]
) -> ClientContext:
    """Scopes the session to a business the user joined as a client (the client app)."""
    set_tenant(session, tenant_id)
    client_id = session.execute(text("SELECT app.current_client_id()")).scalar()
    if client_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_a_client")
    if not has_module(session, "client_app"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    return ClientContext(session=session, tenant_id=tenant_id, client_id=client_id)


ClientDep = Annotated[ClientContext, Depends(get_client_context)]
