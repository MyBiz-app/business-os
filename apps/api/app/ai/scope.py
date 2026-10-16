"""Which branches an AI conversation may see.

effective = the user's branches ∩ the agent's scope ∩ the chat's scope. It is applied for the
whole time the tools run: the request's branch settings (`app.location_ids`, read by
`app.in_branch`) are narrowed, and so is the `TenantContext` the API functions the tools call
check (`ensure_branch_visible`). Scope only ever narrows: an agent cannot see a branch its user
cannot."""

import dataclasses
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.agents import Agent
from app.api.deps import TenantContext

# Matches no branch: an empty scope must see nothing, not everything (an empty array means
# "no restriction" to app.in_branch).
NO_BRANCH = UUID(int=0)


def _group_locations(db: Session, group_ids: frozenset[UUID]) -> frozenset[UUID]:
    """The branches of branch groups. Groups arrive with a later slice (G1); until then a scope
    that names groups resolves to no branch at all (fail closed)."""
    return frozenset()


def agent_branches(db: Session, agent: Agent) -> frozenset[UUID] | None:
    """The branches the agent is limited to; None means it is not limited."""
    if agent.location_scope == "locations":
        return agent.location_ids
    if agent.location_scope == "groups":
        return _group_locations(db, agent.location_group_ids)
    return None


def _current_branch(db: Session) -> UUID | None:
    value = db.execute(text("SELECT app.current_location_id()")).scalar()
    return value


def effective_branches(
    db: Session,
    tenant: TenantContext,
    agent_scope: frozenset[UUID] | None,
    chat_scope: frozenset[UUID] | None,
) -> frozenset[UUID] | None:
    """The branches to work in, or None to leave the request's own settings alone (neither the
    agent nor the chat narrows anything)."""
    if agent_scope is None and chat_scope is None:
        return None
    current = _current_branch(db)
    base: frozenset[UUID] | None = frozenset({current}) if current else tenant.branches
    for narrowing in (agent_scope, chat_scope):
        if narrowing is not None:
            base = narrowing if base is None else base & narrowing
    return base if base is not None else frozenset()


def _set(db: Session, name: str, value: str) -> None:
    db.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


@contextmanager
def narrowed(db: Session, tenant: TenantContext, branches: frozenset[UUID] | None) -> Iterator[Any]:
    """Runs the block with the request narrowed to `branches` (None: unchanged), yielding the
    context to hand to API functions. The previous settings come back afterwards."""
    if branches is None:
        yield tenant
        return
    saved = {
        name: db.execute(
            text("SELECT coalesce(current_setting(:n, true), '')"), {"n": name}
        ).scalar()
        for name in ("app.location_id", "app.location_ids")
    }
    ids = sorted(str(b) for b in (branches or {NO_BRANCH}))
    _set(db, "app.location_id", "")
    _set(db, "app.location_ids", "{" + ",".join(ids) + "}")
    try:
        yield dataclasses.replace(tenant, branches=branches)
    finally:
        for name, value in saved.items():
            _set(db, name, value)


# SQL for "client `c` belongs to the current branches", the same rule as the client list
# (app/api/clients.py): in a branch-scoped business through the client's "my branches" list,
# otherwise through its home branch; a client on no branch belongs to all. Append it to a query
# whose clients table is aliased `c`.
CLIENT_IN_SCOPE = """(
    CASE WHEN (SELECT network_scope FROM app.tenants WHERE id = app.current_tenant_id())
              = 'branch'
         THEN NOT EXISTS (SELECT 1 FROM app.client_locations cl WHERE cl.client_id = c.id)
              OR EXISTS (SELECT 1 FROM app.client_locations cl
                         WHERE cl.client_id = c.id AND app.in_branch(cl.location_id))
         ELSE c.home_location_id IS NULL OR app.in_branch(c.home_location_id)
    END)"""


def visible_clients(db: Session, client_ids: list[UUID]) -> set[UUID]:
    """Which of the clients are in the current branches."""
    if not client_ids:
        return set()
    rows = db.execute(
        text("SELECT c.id FROM app.clients c WHERE c.id = ANY(:ids) AND " + CLIENT_IN_SCOPE),
        {"ids": client_ids},
    ).scalars()
    return set(rows)
