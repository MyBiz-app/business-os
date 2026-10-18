"""Who a connection is and what it may do: the person who approved it, in the business they
approved, with the permissions they hold right now (a demoted or removed member loses them at
once). Tools run in a READ ONLY transaction: even a bug in a tool could not change anything."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.api.deps import ALL_BRANCH_ROLES, BRANCH_BOUND_ROLES, TenantContext, set_branch
from app.core.config import get_settings
from app.core.db import open_session, session_scope, set_tenant
from app.core.permissions import effective_permissions
from app.mcp.tokens import hash_token

METER = "mcp_calls"


class AccessDenied(Exception):
    """The connection exists but may not work in the business any more; the text is safe to show."""


@dataclass(frozen=True)
class Connection:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    client_name: str
    scopes: tuple[str, ...]


@contextmanager
def anonymous_session(engine: Engine) -> Iterator[Session]:
    """A session for callers that are no signed-in person yet (an app registering, a token)."""
    yield from session_scope(open_session(engine, None))


def authenticate(engine: Engine, token: str) -> Connection | None:
    """The live connection holding this access token, or None (unknown, expired or revoked)."""
    with anonymous_session(engine) as session:
        row = session.execute(
            text("SELECT * FROM app.mcp_authenticate(:hash)"), {"hash": hash_token(token)}
        ).first()
    if row is None:
        return None
    return Connection(row.id, row.tenant_id, row.user_id, row.client_name, tuple(row.scopes))


@contextmanager
def tenant_context(engine: Engine, connection: Connection) -> Iterator[TenantContext]:
    """The connection's person inside its business, in a transaction that cannot write."""
    with contextmanager(session_scope)(open_session(engine, connection.user_id)) as session:
        set_tenant(session, connection.tenant_id)
        member = session.execute(
            text("""
                SELECT m.role, r.permissions AS custom_permissions, m.location_ids
                FROM app.tenant_members m
                LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
                WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = app.current_user_id()
            """)
        ).first()
        if member is None:
            raise AccessDenied("You are no longer a member of this business.")
        closed, suspended = session.execute(
            text("""
                SELECT closed_at IS NOT NULL,
                       coalesce(cancel_at <= now() OR billing_state = 'suspended', false)
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        ).one()
        if closed:
            raise AccessDenied("This business is closed.")
        if suspended:
            raise AccessDenied("This business's MyBiz subscription is suspended.")
        allowed = (
            frozenset(member.location_ids)
            if (member.location_ids or member.role in BRANCH_BOUND_ROLES)
            and member.role not in ALL_BRANCH_ROLES
            else None
        )
        if allowed is not None and not allowed:
            raise AccessDenied("You have no branches in this business.")
        set_branch(session, None, allowed)
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield TenantContext(
            session=session,
            tenant_id=connection.tenant_id,
            role=member.role,
            permissions=effective_permissions(member.role, member.custom_permissions),
            branches=allowed,
        )


def count_call(engine: Engine, connection: Connection, tool: str) -> bool:
    """Counts one tool call as usage for the business and for the connection. Returns False, and
    counts nothing, once the business used up its calls for the last 24 hours."""
    limit = get_settings().mcp_daily_calls_per_business
    with contextmanager(session_scope)(open_session(engine, connection.user_id)) as session:
        set_tenant(session, connection.tenant_id)
        if limit:
            used = session.execute(
                text("""
                    SELECT count(*) FROM app.usage_events
                    WHERE tenant_id = app.current_tenant_id() AND meter = :meter
                      AND occurred_at > now() - interval '24 hours'
                """),
                {"meter": METER},
            ).scalar_one()
            if used >= limit:
                return False
        session.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (app.current_tenant_id(), :meter, 1, :details, :ref)
            """),
            {
                "meter": METER,
                "details": json.dumps(
                    {
                        "tool": tool,
                        "client": connection.client_name,
                        "user_id": str(connection.user_id),
                    }
                ),
                "ref": f"mcp_connection:{connection.id}",
            },
        )
        session.execute(
            text("""
                UPDATE app.mcp_connections SET calls = calls + 1, last_used_at = now()
                WHERE id = :id
            """),
            {"id": connection.id},
        )
    return True
