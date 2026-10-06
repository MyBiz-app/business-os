"""Resources: courts, rooms and spaces reserved by the hour (migration 0044, decision X9).

A bookable room has weekly opening hours and serves resource services (a padel court, a
rehearsal room). Free times come from the room's hours minus its scheduled sessions, for every
length the service offers. Reserving creates a one-person session in the room through
app.create_resource_session, which re-checks everything and fixes the price, then books the
client into it, like appointments do with a staff member's time."""

import datetime as dt
from datetime import UTC, datetime, time, timedelta
from itertools import pairwise
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.appointments import HoursBlock
from app.api.bookings import Booking, _load, place_booking
from app.api.client_app import ClientSession, _load_session
from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.api.health import ensure_may_book
from app.appointments import Hours, free_starts
from app.notifications import notify_booking
from app.permissions import Permission
from app.scheduling import local_to_utc

router = APIRouter(tags=["resources"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]


class RoomHours(BaseModel):
    room_id: UUID
    blocks: list[HoursBlock]


class ResourceRoom(BaseModel):
    id: UUID
    name: str
    location_id: UUID
    location_name: str
    capacity: int | None


class ResourceService(BaseModel):
    id: UUID
    name: str
    description: str | None
    color: str | None
    min_minutes: int
    max_minutes: int
    step_minutes: int
    price_per_hour: int
    price_currency: str
    rooms: list[ResourceRoom]


class ResourceSlot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    room_id: UUID
    room_name: str
    price_amount: int
    price_currency: str


class ReservationFields(BaseModel):
    service_id: UUID
    room_id: UUID
    starts_at: datetime
    minutes: int = Field(ge=15, le=1440)


class ReservationCreate(ReservationFields):
    client_id: UUID


# --- Opening hours --------------------------------------------------------------------------


def _room_hours(db: Session, room_id: UUID) -> RoomHours:
    rows = db.execute(
        text("""
            SELECT weekday, starts, ends FROM app.room_hours
            WHERE room_id = :id ORDER BY weekday, starts
        """),
        {"id": room_id},
    ).mappings()
    return RoomHours(room_id=room_id, blocks=[HoursBlock.model_validate(dict(r)) for r in rows])


def _ensure_room(db: Session, room_id: UUID) -> None:
    if db.execute(text("SELECT 1 FROM app.rooms WHERE id = :id"), {"id": room_id}).scalar() is None:
        raise not_found()


@router.get("/rooms/{room_id}/hours")
def get_room_hours(room_id: UUID, context: ReadDep) -> RoomHours:
    _ensure_room(context.session, room_id)
    return _room_hours(context.session, room_id)


@router.put("/rooms/{room_id}/hours")
def set_room_hours(room_id: UUID, blocks: list[HoursBlock], context: WriteDep) -> RoomHours:
    """Replaces the room's weekly opening hours (blocks may not overlap)."""
    db = context.session
    _ensure_room(db, room_id)
    ordered = sorted(blocks, key=lambda b: (b.weekday, b.starts))
    for previous, current in pairwise(ordered):
        if previous.weekday == current.weekday and current.starts < previous.ends:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="overlapping_hours"
            )
    db.execute(text("DELETE FROM app.room_hours WHERE room_id = :id"), {"id": room_id})
    if ordered:
        db.execute(
            text("""
                INSERT INTO app.room_hours (tenant_id, room_id, weekday, starts, ends)
                VALUES (:tenant_id, :room_id, :weekday, :starts, :ends)
            """),
            [
                {"tenant_id": context.tenant_id, "room_id": room_id, **block.model_dump()}
                for block in ordered
            ],
        )
    return _room_hours(db, room_id)


@router.put("/services/{service_id}/rooms")
def set_service_rooms(
    service_id: UUID, room_ids: list[UUID], context: WriteDep
) -> list[ResourceRoom]:
    """Which bookable rooms serve a resource service (replaces the list)."""
    db = context.session
    is_resource = db.execute(
        text("SELECT booking_mode = 'resource' FROM app.services WHERE id = :id"),
        {"id": service_id},
    ).scalar()
    if is_resource is None:
        raise not_found()
    if not is_resource:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_a_resource")
    found = db.execute(
        text("SELECT count(*) FROM app.rooms WHERE id = ANY(:ids) AND bookable"),
        {"ids": list(set(room_ids))},
    ).scalar_one()
    if found != len(set(room_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="room_not_bookable"
        )
    db.execute(text("DELETE FROM app.service_rooms WHERE service_id = :id"), {"id": service_id})
    if room_ids:
        db.execute(
            text("""
                INSERT INTO app.service_rooms (tenant_id, service_id, room_id)
                VALUES (:tenant_id, :service_id, :room_id)
            """),
            [
                {"tenant_id": context.tenant_id, "service_id": service_id, "room_id": room_id}
                for room_id in set(room_ids)
            ],
        )
    return _services(db, service_id=service_id)[0].rooms


# --- What can be reserved ---------------------------------------------------------------------


def _services(db: Session, *, service_id: UUID | None = None) -> list[ResourceService]:
    """Active resource services with their active, bookable rooms in active branches."""
    where = "AND sv.id = :id" if service_id else "AND sv.active"
    services = db.execute(
        text(f"""
            SELECT sv.id, sv.name, sv.description, sv.color, sv.min_minutes, sv.max_minutes,
                   sv.step_minutes, sv.price_per_hour, sv.price_currency
            FROM app.services sv WHERE sv.booking_mode = 'resource' {where}
            ORDER BY sv.name
        """),
        {"id": service_id},
    ).mappings()
    rooms = db.execute(
        text("""
            SELECT sr.service_id, r.id, r.name, r.location_id, l.name AS location_name, r.capacity
            FROM app.service_rooms sr
            JOIN app.rooms r ON r.id = sr.room_id AND r.active AND r.bookable
            JOIN app.locations l ON l.id = r.location_id AND l.active
            WHERE app.in_branch(r.location_id)
            ORDER BY l.name, r.name
        """)
    ).mappings()
    by_service: dict[UUID, list[ResourceRoom]] = {}
    for row in rooms:
        by_service.setdefault(row["service_id"], []).append(ResourceRoom.model_validate(dict(row)))
    return [
        ResourceService.model_validate({**row, "rooms": by_service.get(row["id"], [])})
        for row in services
    ]


def lengths(service: ResourceService) -> list[int]:
    """The lengths, in minutes, a client may choose for the service."""
    return list(range(service.min_minutes, service.max_minutes + 1, service.step_minutes))


def price_of(price_per_hour: int, minutes: int) -> int:
    """Price in minor units for a stretch of time, rounded like the database does."""
    return int((price_per_hour * minutes + 30) // 60)


def resource_slots(
    db: Session, service_id: UUID, day: dt.date, minutes: int, room_id: UUID | None
) -> list[ResourceSlot]:
    """Free start times on a local day for one length, in every room (or one room)."""
    found = _services(db, service_id=service_id)
    if not found or not found[0].rooms:
        raise not_found()
    service = found[0]
    if minutes not in lengths(service):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="length_not_offered"
        )
    business = (
        db.execute(
            text("""
                SELECT t.time_zone,
                       EXISTS (SELECT 1 FROM app.closed_days d
                               WHERE d.tenant_id = t.id AND d.day = :day) AS closed
                FROM app.tenants t
                WHERE t.id = coalesce(app.current_tenant_id(), app.client_tenant_id())
            """),
            {"day": day},
        )
        .mappings()
        .one()
    )
    if business["closed"]:
        return []
    rooms = [r for r in service.rooms if room_id is None or r.id == room_id]
    ids = [r.id for r in rooms]
    hours = db.execute(
        text("""
            SELECT room_id, starts, ends FROM app.room_hours
            WHERE weekday = :weekday AND room_id = ANY(:ids)
        """),
        {"weekday": day.weekday(), "ids": ids},
    ).all()
    day_start = local_to_utc(day, time.min, business["time_zone"])
    busy = db.execute(
        text("""
            SELECT room_id, starts_at, ends_at FROM app.sessions
            WHERE room_id = ANY(:ids) AND status = 'scheduled'
              AND starts_at < :to AND ends_at > :from
        """),
        {"ids": ids, "from": day_start, "to": day_start + timedelta(days=1, hours=1)},
    ).all()
    length = timedelta(minutes=minutes)
    price = price_of(service.price_per_hour, minutes)
    slots = [
        ResourceSlot(
            starts_at=start,
            ends_at=start + length,
            room_id=room.id,
            room_name=room.name,
            price_amount=price,
            price_currency=service.price_currency,
        )
        for room in rooms
        for start in free_starts(
            day,
            [Hours(h.starts, h.ends) for h in hours if h.room_id == room.id],
            [(b.starts_at, b.ends_at) for b in busy if b.room_id == room.id],
            minutes,
            business["time_zone"],
            now=datetime.now(UTC),
        )
    ]
    return sorted(slots, key=lambda slot: (slot.starts_at, slot.room_name))


def create_resource_session(db: Session, body: ReservationFields) -> UUID:
    if body.starts_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_started")
    try:
        with db.begin_nested():
            return db.execute(
                text("SELECT app.create_resource_session(:service, :room, :starts, :minutes)"),
                {
                    "service": body.service_id,
                    "room": body.room_id,
                    "starts": body.starts_at,
                    "minutes": body.minutes,
                },
            ).scalar_one()
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None) or ""
        detail = {
            "23P01": "slot_taken",  # the function's check, or the exclusion constraint
            "22023": "outside_hours",
            "22003": "length_not_offered",
            "P0002": "not_found",
        }.get(code)
        if detail is None:
            raise
        if detail == "not_found":
            raise not_found() from error
        status_code = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
            if detail == "length_not_offered"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=detail) from error


# --- Staff ------------------------------------------------------------------------------------


@router.get("/resources")
def resource_services(context: ReadDep) -> list[ResourceService]:
    return _services(context.session)


@router.get("/resources/slots")
def resource_free_times(
    context: ReadDep,
    service_id: Annotated[UUID, Query()],
    day: Annotated[dt.date, Query(alias="date")],
    minutes: Annotated[int, Query(ge=15, le=1440)],
    room_id: Annotated[UUID | None, Query()] = None,
) -> list[ResourceSlot]:
    return resource_slots(context.session, service_id, day, minutes, room_id)


@router.post("/resources/reservations", status_code=status.HTTP_201_CREATED)
def reserve(body: ReservationCreate, context: ManageDep) -> Booking:
    """Reserves a room for a client (a phone call, a walk-in)."""
    db = context.session
    session_id = create_resource_session(db, body)
    booking_id = place_booking(
        db, context.tenant_id, session_id, body.client_id, requires_plan=False
    )
    notify_booking(db, booking_id, "booked_by_studio")
    return _load(db, booking_id)


# --- Clients ----------------------------------------------------------------------------------


@client_router.get("/resources")
def my_resource_services(context: ClientDep) -> list[ResourceService]:
    """What the client can reserve, with the rooms that serve each."""
    return [s for s in _services(context.session) if s.rooms]


@client_router.get("/resources/slots")
def my_resource_free_times(
    context: ClientDep,
    service_id: Annotated[UUID, Query()],
    day: Annotated[dt.date, Query(alias="date")],
    minutes: Annotated[int, Query(ge=15, le=1440)],
    room_id: Annotated[UUID | None, Query()] = None,
) -> list[ResourceSlot]:
    return resource_slots(context.session, service_id, day, minutes, room_id)


@client_router.post("/resources/reservations", status_code=status.HTTP_201_CREATED)
def reserve_mine(body: ReservationFields, context: ClientDep) -> ClientSession:
    """The signed-in client reserves a free time (the business's booking rules apply)."""
    db = context.session
    ensure_may_book(db, context.tenant_id, context.client_id)
    session_id = create_resource_session(db, body)
    place_booking(db, context.tenant_id, session_id, context.client_id, requires_plan=False)
    return _load_session(db, session_id)
