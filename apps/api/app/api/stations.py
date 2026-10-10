"""Stations: the named rooms, desks or posts of a branch that shifts are planned into.

The owner defines them per branch ("Pilates 1", "Yoga 2", "Kitchen"); a shift may name one, and
several people may share a station at the same time. Like shifts, stations follow the current
branch (`app.in_branch`)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.api.shifts import _branch_visible
from app.core.permissions import Permission

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]


class StationFields(BaseModel):
    name: str = Field(min_length=1, max_length=40, description='E.g. "Pilates 1"')

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class StationCreate(StationFields):
    location_id: UUID


class StationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    sort_order: int | None = Field(default=None, ge=0, le=999)

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Station(StationCreate):
    id: UUID
    sort_order: int


STATION_SELECT = """
    SELECT id, location_id, name, sort_order FROM app.stations WHERE app.in_branch(location_id)
"""


def _name_taken(context: TenantContext, location_id: UUID, name: str, ignore: UUID | None) -> bool:
    return (
        context.session.execute(
            text("""
                SELECT 1 FROM app.stations
                WHERE location_id = :l AND lower(name) = lower(:n)
                  AND (CAST(:ignore AS uuid) IS NULL OR id <> CAST(:ignore AS uuid))
            """),
            {"l": location_id, "n": name, "ignore": ignore},
        ).first()
        is not None
    )


@router.get("/stations")
def list_stations(
    context: ReadDep,
    location_id: Annotated[list[UUID] | None, Query(description="Only these branches")] = None,
) -> list[Station]:
    rows = context.session.execute(
        text(
            f"{STATION_SELECT} AND (CAST(:locations AS uuid[]) IS NULL"
            " OR location_id = ANY(CAST(:locations AS uuid[]))) ORDER BY sort_order, name"
        ),
        {"locations": [str(i) for i in location_id] if location_id else None},
    ).mappings()
    return [Station.model_validate(dict(row)) for row in rows]


@router.post("/stations", status_code=status.HTTP_201_CREATED)
def create_station(body: StationCreate, context: ManageDep) -> Station:
    if not _branch_visible(context.session, body.location_id):
        raise HTTPException(status_code=422, detail="invalid_reference")
    if _name_taken(context, body.location_id, body.name, None):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="station_name_taken")
    row = context.session.execute(
        text("""
            INSERT INTO app.stations (tenant_id, location_id, name, sort_order)
            VALUES (app.current_tenant_id(), :location_id, :name,
                    (SELECT coalesce(max(sort_order) + 1, 0) FROM app.stations
                     WHERE location_id = :location_id))
            RETURNING id, location_id, name, sort_order
        """),
        body.model_dump(),
    ).mappings()
    return Station.model_validate(dict(row.one()))


@router.patch("/stations/{station_id}")
def update_station(station_id: UUID, body: StationUpdate, context: ManageDep) -> Station:
    current = (
        context.session.execute(text(f"{STATION_SELECT} AND id = :id"), {"id": station_id})
        .mappings()
        .first()
    )
    if current is None:
        raise not_found()
    merged = {**current, **body.model_dump(exclude_none=True)}
    if _name_taken(context, current["location_id"], merged["name"], station_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="station_name_taken")
    context.session.execute(
        text("UPDATE app.stations SET name = :name, sort_order = :sort_order WHERE id = :id"),
        {"id": station_id, "name": merged["name"], "sort_order": merged["sort_order"]},
    )
    return Station.model_validate({**merged})


@router.delete("/stations/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_station(station_id: UUID, context: ManageDep) -> None:
    """Removes the station; its shifts stay, without a station."""
    deleted = context.session.execute(
        text("DELETE FROM app.stations WHERE id = :id AND app.in_branch(location_id)"),
        {"id": station_id},
    )
    if deleted.rowcount == 0:
        raise not_found()
