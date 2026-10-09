from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import TenantContext, require
from app.core.permissions import Permission

router = APIRouter(tags=["locations"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]

LOCATION_COLUMNS = "id, name, address, active, created_at, updated_at"
ROOM_COLUMNS = "id, location_id, name, capacity, active, bookable"


def _strip_required(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value.strip()


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("address", mode="before")
    @classmethod
    def blank_address(cls, value: object) -> object:
        return blank_to_none(value)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    active: bool | None = None

    @field_validator("address", mode="before")
    @classmethod
    def blank_address(cls, value: object) -> object:
        return blank_to_none(value)


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    bookable: bool | None = Field(
        default=None, description="Reserved by the hour (a court, a room)"
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    active: bool | None = None
    bookable: bool | None = None


class Room(BaseModel):
    id: UUID
    location_id: UUID
    name: str
    capacity: int | None
    active: bool
    bookable: bool


class Location(BaseModel):
    id: UUID
    name: str
    address: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    rooms: list[Room]


def _load_locations(session: Session, location_id: UUID | None = None) -> list[Location]:
    where, params = ("WHERE id = :id", {"id": location_id}) if location_id else ("", {})
    locations = session.execute(
        text(
            f"SELECT {LOCATION_COLUMNS} FROM app.locations {where}"
            " ORDER BY active DESC, created_at, name"
        ),
        params,
    ).mappings()
    rooms_by_location: dict[UUID, list[Room]] = {}
    room_where = "WHERE location_id = :id" if location_id else ""
    for row in session.execute(
        text(f"SELECT {ROOM_COLUMNS} FROM app.rooms {room_where} ORDER BY active DESC, name"),
        params,
    ).mappings():
        rooms_by_location.setdefault(row["location_id"], []).append(Room.model_validate(dict(row)))
    return [
        Location.model_validate({**row, "rooms": rooms_by_location.get(row["id"], [])})
        for row in locations
    ]


def _one_location(session: Session, location_id: UUID) -> Location:
    found = _load_locations(session, location_id)
    if not found:
        raise not_found()
    return found[0]


@router.get("/locations")
def list_locations(context: ReadDep) -> list[Location]:
    """The business's branches; a member kept to some branches sees only theirs (#64)."""
    locations = _load_locations(context.session)
    if context.branches is None:
        return locations
    return [location for location in locations if location.id in context.branches]


@router.post("/locations", status_code=status.HTTP_201_CREATED)
def create_location(body: LocationCreate, context: WriteDep) -> Location:
    location_id = context.session.execute(
        text("""
            INSERT INTO app.locations (tenant_id, name, address)
            VALUES (:tenant_id, :name, :address) RETURNING id
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id},
    ).scalar_one()
    return _one_location(context.session, location_id)


@router.get("/locations/{location_id}")
def get_location(location_id: UUID, context: ReadDep) -> Location:
    return _one_location(context.session, location_id)


@router.patch("/locations/{location_id}")
def update_location(location_id: UUID, body: LocationUpdate, context: WriteDep) -> Location:
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if not (key in {"name", "active"} and value is None)
    }
    if changes.get("active") is False:
        # A business always keeps at least one active branch.
        others = context.session.execute(
            text("SELECT count(*) FROM app.locations WHERE active AND id <> :id"),
            {"id": location_id},
        ).scalar_one()
        if others == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_branch")
    updated = context.session.execute(
        text(f"UPDATE app.locations SET {set_clause(changes)} WHERE id = :id RETURNING id"),
        {**changes, "id": location_id},
    ).first()
    if updated is None:
        raise not_found()
    return _one_location(context.session, location_id)


@router.post("/locations/{location_id}/rooms", status_code=status.HTTP_201_CREATED)
def create_room(location_id: UUID, body: RoomCreate, context: WriteDep) -> Room:
    # The location must be visible to this tenant (RLS); otherwise it does not exist for us.
    row = (
        context.session.execute(
            text(f"""
                INSERT INTO app.rooms (tenant_id, location_id, name, capacity, bookable)
                SELECT l.tenant_id, l.id, :name, :capacity, coalesce(:bookable, false)
                FROM app.locations l WHERE l.id = :id
                RETURNING {ROOM_COLUMNS}
            """),
            {**body.model_dump(), "id": location_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Room.model_validate(dict(row))


@router.patch("/rooms/{room_id}")
def update_room(room_id: UUID, body: RoomUpdate, context: WriteDep) -> Room:
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if not (key in {"name", "active", "bookable"} and value is None)
    }
    sql = f"UPDATE app.rooms SET {set_clause(changes)} WHERE id = :id RETURNING {ROOM_COLUMNS}"
    row = (
        context.session.execute(
            text(sql),
            {**changes, "id": room_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Room.model_validate(dict(row))
