"""Branch groups: a named set of branches ("South district") that a screen, a message or an AI
agent can be pointed at together. A branch may be in several groups. Everyone who can read the
catalog sees the groups, but only the branches they may see; the owner manages them."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.core.permissions import Permission

router = APIRouter(tags=["locations"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

GROUP_SELECT = """
    SELECT g.id, g.name,
           coalesce(array_agg(m.location_id ORDER BY l.name, l.id)
                    FILTER (WHERE m.location_id IS NOT NULL AND app.in_branch(m.location_id)),
                    '{}') AS location_ids
    FROM app.location_groups g
    LEFT JOIN app.location_group_members m ON m.group_id = g.id
    LEFT JOIN app.locations l ON l.id = m.location_id
"""
GROUP_TAIL = " GROUP BY g.id ORDER BY g.sort_order, lower(g.name)"
ONE_GROUP = text(GROUP_SELECT + " WHERE g.id = :id GROUP BY g.id")


class GroupFields(BaseModel):
    name: str = Field(min_length=1, max_length=60, description='E.g. "South district"')
    location_ids: list[UUID] = Field(default_factory=list, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    location_ids: list[UUID] | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LocationGroup(BaseModel):
    id: UUID
    name: str
    location_ids: list[UUID] = Field(description="The branches in the group that you may see")


def _one(session: Session, group_id: UUID) -> LocationGroup:
    row = session.execute(ONE_GROUP, {"id": group_id}).mappings().first()
    if row is None:
        raise not_found()
    return LocationGroup.model_validate(dict(row))


def _set_members(session: Session, group_id: UUID, location_ids: list[UUID]) -> None:
    """Replaces the members; every branch must exist in this business (else 422)."""
    wanted = list(dict.fromkeys(location_ids))
    found = session.execute(
        text("SELECT count(*) FROM app.locations WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(i) for i in wanted]},
    ).scalar_one()
    if found != len(wanted):
        raise HTTPException(status_code=422, detail="invalid_reference")
    session.execute(
        text("DELETE FROM app.location_group_members WHERE group_id = :g"), {"g": group_id}
    )
    session.execute(
        text("""
            INSERT INTO app.location_group_members (tenant_id, group_id, location_id)
            SELECT app.current_tenant_id(), :g, CAST(x AS uuid)
            FROM unnest(CAST(:ids AS text[])) AS x
        """),
        {"g": group_id, "ids": [str(i) for i in wanted]},
    )


def _name_conflict() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="group_name_taken")


@router.get("/location-groups")
def list_location_groups(context: ReadDep) -> list[LocationGroup]:
    rows = context.session.execute(text(GROUP_SELECT + GROUP_TAIL)).mappings()
    return [LocationGroup.model_validate(dict(row)) for row in rows]


@router.post("/location-groups", status_code=status.HTTP_201_CREATED)
def create_location_group(body: GroupFields, context: SettingsDep) -> LocationGroup:
    try:
        group_id = context.session.execute(
            text("""
                INSERT INTO app.location_groups (tenant_id, name, sort_order)
                VALUES (app.current_tenant_id(), :name,
                        (SELECT coalesce(max(sort_order) + 1, 0) FROM app.location_groups))
                RETURNING id
            """),
            {"name": body.name},
        ).scalar_one()
    except IntegrityError:
        raise _name_conflict() from None
    _set_members(context.session, group_id, body.location_ids)
    return _one(context.session, group_id)


@router.patch("/location-groups/{group_id}")
def update_location_group(group_id: UUID, body: GroupUpdate, context: SettingsDep) -> LocationGroup:
    _one(context.session, group_id)
    if body.name is not None:
        try:
            context.session.execute(
                text("UPDATE app.location_groups SET name = :name WHERE id = :id"),
                {"id": group_id, "name": body.name},
            )
        except IntegrityError:
            raise _name_conflict() from None
    if body.location_ids is not None:
        _set_members(context.session, group_id, body.location_ids)
    return _one(context.session, group_id)


@router.delete("/location-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location_group(group_id: UUID, context: SettingsDep) -> None:
    """Removes the group only; its branches stay."""
    deleted = context.session.execute(
        text("DELETE FROM app.location_groups WHERE id = :id"), {"id": group_id}
    )
    if deleted.rowcount == 0:
        raise not_found()
