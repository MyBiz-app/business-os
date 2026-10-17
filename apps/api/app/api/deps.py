import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.db import EngineDep, open_session, session_scope, set_tenant
from app.core.mfa import (
    SENSITIVE_PERMISSIONS,
    mfa_required,
    require_aal2,
    sensitive_action_needs_mfa,
)
from app.core.permissions import Permission, effective_permissions

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
    # The branches this person may work in; None means every branch (#64).
    branches: frozenset[UUID] | None = None
    # "aal2" once the person entered an authenticator code (app/core/mfa.py).
    aal: str = "aal1"


def ensure_branch_visible(context: TenantContext, location_id: UUID | None) -> None:
    """Reading or changing something by id: a member kept to some branches gets "not found" for
    anything filed under another one. A row with no branch belongs to everyone."""
    if (
        context.branches is not None
        and location_id is not None
        and location_id not in context.branches
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


def ensure_branch_allowed(context: TenantContext, location_id: UUID | None) -> None:
    """A branch named in a request body: a member kept to some branches can't file anything
    under another one."""
    if (
        context.branches is not None
        and location_id is not None
        and location_id not in context.branches
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_branch"
        )


def ensure_client_visible(context: TenantContext, client_id: UUID | None) -> None:
    """Anything filed under a client (notes, documents, health declarations, dependents,
    receipts, quotes) follows the client's home branch: a member kept to some branches gets
    "not found" for another branch's client. A client with no home branch belongs to everyone."""
    if context.branches is None or client_id is None:
        return
    home = context.session.execute(
        text("SELECT home_location_id FROM app.clients WHERE id = :id"), {"id": client_id}
    ).first()
    if home is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    ensure_branch_visible(context, home.home_location_id)


def client_branch_filter(context: TenantContext, home_column: str) -> tuple[str, dict]:
    """SQL condition and parameters keeping a list to clients whose home branch the member may
    reach (`home_column` is the client's `home_location_id`); no condition for everyone else."""
    if context.branches is None:
        return "TRUE", {}
    return (
        f"({home_column} IS NULL OR {home_column} = ANY(CAST(:visible_branches AS uuid[])))",
        {"visible_branches": list(context.branches)},
    )


def _audit_platform_visit(session: Session, tenant_id: UUID, action: str, request: Request) -> None:
    """Writes the visit to the business's own audit log, which its owner reads in settings."""
    session.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            SELECT :tenant_id, 'platform', u.id, CAST(:action AS text),
                   jsonb_build_object('method', CAST(:method AS text), 'path', CAST(:path AS text),
                                      'email', u.email)
            FROM app.users u WHERE u.id = app.current_user_id()
        """),
        {
            "tenant_id": tenant_id,
            "action": action,
            "method": request.method,
            "path": request.url.path,
        },
    )


def _support_context(
    session: Session, tenant_id: UUID, request: Request, aal: str
) -> TenantContext:
    """A MyBiz staff member inside a business that granted support access: every request is
    audited for the owner, and the transaction is READ ONLY at the database level."""
    _audit_platform_visit(session, tenant_id, "support.view", request)
    session.execute(text("SET TRANSACTION READ ONLY"))
    return TenantContext(
        session=session,
        tenant_id=tenant_id,
        role="support",
        permissions=effective_permissions("support", None),
        aal=aal,
    )


def _platform_context(
    session: Session, tenant_id: UUID, request: Request, aal: str
) -> TenantContext:
    """A MyBiz staff member with `businesses.act` working in a business for its owner: they can
    fix things like a manager, and every request (reads and changes alike) is audited for the
    owner and for MyBiz."""
    action = "platform.view" if request.method in ("GET", "HEAD", "OPTIONS") else "platform.change"
    _audit_platform_visit(session, tenant_id, action, request)
    if action == "platform.change":
        session.execute(
            text("SELECT app.platform_audit_add(:action, :tenant, :details)"),
            {
                "action": action,
                "tenant": tenant_id,
                "details": json.dumps({"method": request.method, "path": request.url.path}),
            },
        )
    return TenantContext(
        session=session,
        tenant_id=tenant_id,
        role="platform",
        permissions=effective_permissions("platform", None),
        aal=aal,
    )


# Roles that always work across every branch; others with branches assigned are kept to them.
ALL_BRANCH_ROLES = frozenset({"owner", "manager"})
# Roles that exist only inside their branches: none assigned means no access, never "all".
BRANCH_BOUND_ROLES = frozenset({"branch_manager"})


def set_branch(
    session: Session, location_id: UUID | None, allowed: frozenset[UUID] | None = None
) -> None:
    """The branch this request works in: lists and numbers follow it (app.in_branch) and new
    sessions, sales and clients are filed under it. It must be one of the business's branches.
    A member kept to some branches (`allowed`) works only in those: no branch, or one outside
    them, means all of their branches."""
    if allowed is not None and location_id not in allowed:
        if len(allowed) == 1:
            location_id = next(iter(allowed))
        else:
            session.execute(
                text("SELECT set_config('app.location_ids', :ids, true)"),
                {"ids": "{" + ",".join(sorted(str(b) for b in allowed)) + "}"},
            )
            return
    if location_id is None:
        return
    known = session.execute(
        text("SELECT EXISTS (SELECT 1 FROM app.locations WHERE id = :id)"), {"id": location_id}
    ).scalar_one()
    if not known:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_branch"
        )
    session.execute(
        text("SELECT set_config('app.location_id', :id, true)"), {"id": str(location_id)}
    )


def get_tenant_context(
    session: SessionDep,
    user: UserDep,
    tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")],
    request: Request,
    branch_id: Annotated[
        UUID | None,
        Header(alias="X-Location-Id", description="The current branch (none: all branches)"),
    ] = None,
) -> TenantContext:
    """Scopes the session to one tenant (and optionally one of its branches). Fails unless the
    user is a member of that tenant (or platform support the business let in)."""
    set_tenant(session, tenant_id)
    member = session.execute(
        text("""
            SELECT m.role, r.permissions AS custom_permissions, m.location_ids
            FROM app.tenant_members m
            LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
            WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = app.current_user_id()
        """)
    ).first()
    if member is None:
        if session.execute(text("SELECT app.support_tenant_id()")).scalar() is not None:
            require_aal2(user.aal)
            context = _support_context(session, tenant_id, request, user.aal)
            set_branch(session, branch_id)
            return context
        if session.execute(text("SELECT app.platform_act_tenant_id()")).scalar() is not None:
            require_aal2(user.aal)
            context = _platform_context(session, tenant_id, request, user.aal)
            set_branch(session, branch_id)
            return context
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_a_member")
    allowed = (
        frozenset(member.location_ids)
        if (member.location_ids or member.role in BRANCH_BOUND_ROLES)
        and member.role not in ALL_BRANCH_ROLES
        else None
    )
    if allowed is not None and not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_branches")
    if (
        not request.url.path.startswith("/tenants/current/closure")
        and session.execute(
            text("SELECT closed_at IS NOT NULL FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="business_closed")
    if (
        user.aal != "aal2"
        and get_settings().mfa_on
        and session.execute(
            text("SELECT require_mfa_for_staff FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar()
    ):
        raise mfa_required()
    set_branch(session, branch_id, allowed)
    return TenantContext(
        session=session,
        tenant_id=tenant_id,
        role=member.role,
        permissions=effective_permissions(member.role, member.custom_permissions),
        branches=allowed,
        aal=user.aal,
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
        if permission in SENSITIVE_PERMISSIONS and sensitive_action_needs_mfa(context.aal):
            raise mfa_required()
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
    if session.execute(
        text("SELECT closed_at IS NOT NULL FROM app.tenants WHERE id = :id"), {"id": tenant_id}
    ).scalar():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="business_closed")
    if not has_module(session, "client_app"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    return ClientContext(session=session, tenant_id=tenant_id, client_id=client_id)


ClientDep = Annotated[ClientContext, Depends(get_client_context)]
