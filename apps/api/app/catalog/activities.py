"""A business's activities: what it starts with and which one a key from the catalog means."""

from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.catalog.verticals_v2 import BUSINESS_TYPES, default_activities, successors_of

Entry = dict[str, Any]


def find_activity(business_type: str, activity_key: str) -> Entry | None:
    """The catalog entry, or none when the type or the key is unknown."""
    entry = BUSINESS_TYPES.get(business_type)
    if entry is None:
        return None
    return next((a for a in entry["activities"] if a["key"] == activity_key), None)


def add_activity(
    session: Session | Connection,
    tenant_id: UUID,
    business_type: str,
    activity: Entry,
    position: int,
) -> None:
    """Adds the activity, or turns a switched-off one back on."""
    session.execute(
        text("""
            INSERT INTO app.tenant_activities
                (tenant_id, business_type, activity_key, model, resource_type, position)
            VALUES (:t, :type, :key, :model, :resource, :position)
            ON CONFLICT (tenant_id, business_type, activity_key)
            DO UPDATE SET enabled = true, updated_at = now()
        """),
        {
            "t": tenant_id,
            "type": business_type,
            "key": activity["key"],
            "model": activity["model"],
            "resource": activity.get("resource_type"),
            "position": position,
        },
    )


def seed_activities(session: Session | Connection, tenant_id: UUID, vertical: str) -> None:
    """A new business starts with its industry's default activities. Branches created afterwards
    are linked to them by a database trigger."""
    types = successors_of(vertical)
    if not types:
        return
    business_type = types[0]["key"]
    for position, activity in enumerate(default_activities(business_type)):
        add_activity(session, tenant_id, business_type, activity, position)
