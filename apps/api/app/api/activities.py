from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, ensure_branch_visible, require
from app.catalog.activities import add_activity, find_activity
from app.core.permissions import Permission

router = APIRouter(tags=["activities"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]


class TenantActivity(BaseModel):
    id: UUID
    business_type: str = Field(description="The catalog business type the activity came from")
    activity_key: str
    model: str = Field(description="The service model that runs it (appointment, group_class, ...)")
    resource_type: str | None = Field(description="The kind of court or room it books, if any")
    enabled: bool


class ActivityChoice(BaseModel):
    business_type: str = Field(max_length=80)
    activity_key: str = Field(max_length=80)


class ActivitiesSet(BaseModel):
    activities: list[ActivityChoice] = Field(max_length=100)


class BranchActivitiesSet(BaseModel):
    activity_ids: list[UUID] = Field(max_length=100)


def _load(session: Session) -> list[TenantActivity]:
    rows = session.execute(
        text("""
            SELECT id, business_type, activity_key, model, resource_type, enabled
            FROM app.tenant_activities ORDER BY enabled DESC, position, activity_key
        """)
    ).mappings()
    return [TenantActivity.model_validate(dict(row)) for row in rows]


@router.get("/activities")
def list_activities(context: ReadDep) -> list[TenantActivity]:
    """What the business offers, switched-off activities last."""
    return _load(context.session)


@router.put("/activities")
def set_activities(body: ActivitiesSet, context: WriteDep) -> list[TenantActivity]:
    """Replaces the set of activities the business offers. Any catalog business type's activity
    can be chosen (a tennis club may also rent out padel courts); one left out is switched off,
    not deleted. A newly offered activity is linked to every active branch."""
    if context.branches is not None:  # the business's offer is for people who reach every branch
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    chosen = []
    for choice in body.activities:
        entry = find_activity(choice.business_type, choice.activity_key)
        if entry is None or entry.get("coming_soon"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_activity"
            )
        chosen.append((choice.business_type, entry))
    session = context.session
    offered_before = {a.id for a in _load(session) if a.enabled}
    session.execute(text("UPDATE app.tenant_activities SET enabled = false, updated_at = now()"))
    for position, (business_type, entry) in enumerate(chosen):
        add_activity(session, context.tenant_id, business_type, entry, position)
        session.execute(
            text("""
                UPDATE app.tenant_activities SET position = :position
                WHERE business_type = :type AND activity_key = :key
            """),
            {"position": position, "type": business_type, "key": entry["key"]},
        )
    newly_offered = [a.id for a in _load(session) if a.enabled and a.id not in offered_before]
    session.execute(
        text("""
            INSERT INTO app.location_activities (tenant_id, location_id, activity_id)
            SELECT l.tenant_id, l.id, a.id
            FROM app.locations l
            JOIN app.tenant_activities a ON a.id = ANY(:ids)
            WHERE l.active
            ON CONFLICT DO NOTHING
        """),
        {"ids": newly_offered},
    )
    return _load(session)


def _branch_activity_ids(session: Session, location_id: UUID) -> list[UUID]:
    return list(
        session.execute(
            text("""
                SELECT la.activity_id FROM app.location_activities la
                JOIN app.tenant_activities a ON a.id = la.activity_id
                WHERE la.location_id = :id AND a.enabled
                ORDER BY a.position, a.activity_key
            """),
            {"id": location_id},
        ).scalars()
    )


def _ensure_branch(context: TenantContext, location_id: UUID) -> None:
    ensure_branch_visible(context, location_id)
    found = context.session.execute(
        text("SELECT 1 FROM app.locations WHERE id = :id"), {"id": location_id}
    ).first()
    if found is None:
        raise not_found()


@router.get("/locations/{location_id}/activities")
def get_branch_activities(location_id: UUID, context: ReadDep) -> list[UUID]:
    """The ids of the activities this branch offers."""
    _ensure_branch(context, location_id)
    return _branch_activity_ids(context.session, location_id)


@router.put("/locations/{location_id}/activities")
def set_branch_activities(
    location_id: UUID, body: BranchActivitiesSet, context: WriteDep
) -> list[UUID]:
    """Sets which of the business's activities this branch offers."""
    _ensure_branch(context, location_id)
    session = context.session
    wanted = list(dict.fromkeys(body.activity_ids))
    known = set(
        session.execute(
            text("SELECT id FROM app.tenant_activities WHERE enabled AND id = ANY(:ids)"),
            {"ids": wanted},
        ).scalars()
    )
    if known != set(wanted):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_activity"
        )
    session.execute(
        text("DELETE FROM app.location_activities WHERE location_id = :id"), {"id": location_id}
    )
    for activity_id in wanted:
        session.execute(
            text("""
                INSERT INTO app.location_activities (tenant_id, location_id, activity_id)
                VALUES (:t, :l, :a)
            """),
            {"t": context.tenant_id, "l": location_id, "a": activity_id},
        )
    return _branch_activity_ids(session, location_id)
