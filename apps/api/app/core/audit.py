"""One place to write the business's audit log (go-live, GL7).

The log is append-only for the API. `category` is derived by the database from the action's first
part (migration 0114). Details hold ids and names of what changed, never secrets or ID numbers."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def record(
    session: Session,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    tenant_id: UUID | None = None,
    **details: Any,
) -> None:
    """Writes one entry for the signed-in person in the current business (or `tenant_id`)."""
    session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (coalesce(:tenant_id, app.current_tenant_id()), 'user', app.current_user_id(),
                    :action, :entity_type, :entity_id, CAST(:details AS jsonb))
        """),
        {
            "tenant_id": tenant_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": json.dumps(details, default=str),
        },
    )


def record_everywhere(session: Session, action: str, **details: Any) -> None:
    """For things that happen to the person, not to one business (a sign-in from a new device):
    every business they work for gets the entry. Ends with no business selected."""
    from app.core.db import set_tenant

    tenants = (
        session.execute(
            text("SELECT tenant_id FROM app.tenant_members WHERE user_id = app.current_user_id()")
        )
        .scalars()
        .all()
    )
    user_id = session.execute(text("SELECT app.current_user_id()")).scalar_one()
    for tenant_id in tenants:
        set_tenant(session, tenant_id)
        record(session, action, entity_type="user", entity_id=user_id, **details)
