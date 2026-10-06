"""Appointments: one-to-one bookings with a staff member at a free time (migration 0027).

Staff publish weekly working hours. Free times come from those hours minus each staff
member's busy time (`appointment_slots` below). Booking creates a one-person session through
app.create_appointment_session, which re-checks everything, and books the client into it."""

import datetime as dt
from datetime import UTC, datetime, time, timedelta
from itertools import pairwise
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.bookings import Booking, _load, place_booking
from app.api.client_app import ClientSession, _load_session
from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.api.health import ensure_may_book
from app.appointments import Hours, free_starts
from app.notifications import notify_booking
from app.permissions import Permission
from app.scheduling import local_to_utc

router = APIRouter(tags=["appointments"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_WRITE))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]


class HoursBlock(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday … 6 = Sunday")
    starts: time
    ends: time

    @model_validator(mode="after")
    def ends_after_start(self) -> "HoursBlock":
        if self.ends <= self.starts:
            raise ValueError("ends must be after starts")
        return self


class StaffHours(BaseModel):
    user_id: UUID
    blocks: list[HoursBlock]


class AppointmentStaff(BaseModel):
    user_id: UUID
    name: str


class Slot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    staff_user_id: UUID
    staff_name: str


class AppointmentCreate(BaseModel):
    service_id: UUID
    staff_user_id: UUID
    starts_at: datetime
    client_id: UUID


class ClientAppointmentCreate(BaseModel):
    service_id: UUID
    staff_user_id: UUID
    starts_at: datetime


# --- Working hours ----------------------------------------------------------------------------


def _hours(db: Session, user_id: UUID) -> StaffHours:
    rows = db.execute(
        text("""
            SELECT weekday, starts, ends FROM app.staff_hours
            WHERE user_id = :id ORDER BY weekday, starts
        """),
        {"id": user_id},
    ).mappings()
    return StaffHours(user_id=user_id, blocks=[HoursBlock.model_validate(dict(r)) for r in rows])


@router.get("/staff/{user_id}/hours")
def get_staff_hours(user_id: UUID, context: ReadDep) -> StaffHours:
    return _hours(context.session, user_id)


@router.put("/staff/{user_id}/hours")
def set_staff_hours(user_id: UUID, blocks: list[HoursBlock], context: WriteDep) -> StaffHours:
    """Replaces the staff member's weekly working hours (blocks may not overlap)."""
    db = context.session
    member = db.execute(
        text(
            "SELECT 1 FROM app.tenant_members"
            " WHERE tenant_id = app.current_tenant_id() AND user_id = :id"
        ),
        {"id": user_id},
    ).scalar()
    if member is None:
        raise not_found()
    ordered = sorted(blocks, key=lambda b: (b.weekday, b.starts))
    for previous, current in pairwise(ordered):
        if previous.weekday == current.weekday and current.starts < previous.ends:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="overlapping_hours"
            )
    db.execute(text("DELETE FROM app.staff_hours WHERE user_id = :id"), {"id": user_id})
    for block in ordered:
        db.execute(
            text("""
                INSERT INTO app.staff_hours (tenant_id, user_id, weekday, starts, ends)
                VALUES (:tenant_id, :user_id, :weekday, :starts, :ends)
            """),
            {"tenant_id": context.tenant_id, "user_id": user_id, **block.model_dump()},
        )
    return _hours(db, user_id)


# --- Time off -------------------------------------------------------------------------------


class TimeOffCreate(BaseModel):
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def ordered(self) -> "TimeOffCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must not be before starts_on")
        if (self.ends_on - self.starts_on).days > 366:
            raise ValueError("at most a year at a time")
        return self


class TimeOff(BaseModel):
    id: UUID
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None


@router.get("/staff/{user_id}/time-off")
def list_time_off(user_id: UUID, context: ReadDep) -> list[TimeOff]:
    """The staff member's time off that hasn't ended yet, soonest first."""
    rows = context.session.execute(
        text("""
            SELECT o.id, o.starts_on, o.ends_on, o.reason FROM app.staff_time_off o
            JOIN app.tenants t ON t.id = o.tenant_id
            WHERE o.user_id = :id AND o.ends_on >= (now() AT TIME ZONE t.time_zone)::date
            ORDER BY o.starts_on
        """),
        {"id": user_id},
    ).mappings()
    return [TimeOff.model_validate(dict(r)) for r in rows]


@router.post("/staff/{user_id}/time-off", status_code=status.HTTP_201_CREATED)
def add_time_off(user_id: UUID, body: TimeOffCreate, context: WriteDep) -> TimeOff:
    """Blocks whole days; appointments already booked in them stay (the business handles
    them), but no new ones are offered."""
    db = context.session
    member = db.execute(
        text(
            "SELECT 1 FROM app.tenant_members"
            " WHERE tenant_id = app.current_tenant_id() AND user_id = :id"
        ),
        {"id": user_id},
    ).scalar()
    if member is None:
        raise not_found()
    row = (
        db.execute(
            text("""
                INSERT INTO app.staff_time_off (tenant_id, user_id, starts_on, ends_on, reason)
                VALUES (:t, :u, :starts_on, :ends_on, :reason)
                RETURNING id, starts_on, ends_on, reason
            """),
            {"t": context.tenant_id, "u": user_id, **body.model_dump()},
        )
        .mappings()
        .one()
    )
    return TimeOff.model_validate(dict(row))


@router.delete("/staff/{user_id}/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_time_off(user_id: UUID, time_off_id: UUID, context: WriteDep) -> None:
    deleted = context.session.execute(
        text("DELETE FROM app.staff_time_off WHERE id = :id AND user_id = :u RETURNING id"),
        {"id": time_off_id, "u": user_id},
    ).scalar()
    if deleted is None:
        raise not_found()


# --- Free times -------------------------------------------------------------------------------


def _staff(db: Session) -> list[AppointmentStaff]:
    rows = db.execute(text("SELECT user_id, name FROM app.appointment_staff()")).mappings()
    return [AppointmentStaff.model_validate(dict(r)) for r in rows]


def appointment_slots(
    db: Session, service_id: UUID, day: dt.date, staff_user_id: UUID | None
) -> list[Slot]:
    """Free start times for the service on a local day, per staff member who takes it."""
    service = (
        db.execute(
            text("""
                SELECT duration_minutes FROM app.services
                WHERE id = :id AND active AND booking_mode = 'appointment'
            """),
            {"id": service_id},
        )
        .mappings()
        .first()
    )
    if service is None:
        raise not_found()
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
    staff = [s for s in _staff(db) if staff_user_id is None or s.user_id == staff_user_id]
    hours = db.execute(
        text("SELECT user_id, starts, ends FROM app.staff_hours WHERE weekday = :weekday"),
        {"weekday": day.weekday()},
    ).all()
    day_start = local_to_utc(day, time.min, business["time_zone"])
    busy = db.execute(
        text("SELECT user_id, starts_at, ends_at FROM app.staff_busy(:from, :to)"),
        {"from": day_start, "to": day_start + timedelta(days=1, hours=1)},
    ).all()
    length = timedelta(minutes=service["duration_minutes"])
    slots = [
        Slot(starts_at=start, ends_at=start + length, staff_user_id=s.user_id, staff_name=s.name)
        for s in staff
        for start in free_starts(
            day,
            [Hours(h.starts, h.ends) for h in hours if h.user_id == s.user_id],
            [(b.starts_at, b.ends_at) for b in busy if b.user_id == s.user_id],
            service["duration_minutes"],
            business["time_zone"],
            now=datetime.now(UTC),
        )
    ]
    return sorted(slots, key=lambda slot: (slot.starts_at, slot.staff_name))


def create_appointment_session(
    db: Session, service_id: UUID, staff_user_id: UUID, starts_at: datetime
) -> UUID:
    if starts_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_started")
    try:
        with db.begin_nested():
            return db.execute(
                text("SELECT app.create_appointment_session(:service, :staff, :starts)"),
                {"service": service_id, "staff": staff_user_id, "starts": starts_at},
            ).scalar_one()
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        detail = {"23P01": "slot_taken", "22023": "outside_hours", "P0002": "not_found"}.get(
            code or ""
        )
        if detail is None:
            raise
        if detail == "not_found":
            raise not_found() from error
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error


@router.get("/appointments/staff")
def staff_for_appointments(context: ReadDep) -> list[AppointmentStaff]:
    return _staff(context.session)


@router.get("/appointments/slots")
def slots(
    context: ReadDep,
    service_id: Annotated[UUID, Query()],
    day: Annotated[dt.date, Query(alias="date")],
    staff_user_id: Annotated[UUID | None, Query()] = None,
) -> list[Slot]:
    return appointment_slots(context.session, service_id, day, staff_user_id)


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
def book_appointment(body: AppointmentCreate, context: ManageDep) -> Booking:
    """Books a client into a free time with a staff member (staff may book without a plan)."""
    db = context.session
    session_id = create_appointment_session(db, body.service_id, body.staff_user_id, body.starts_at)
    booking_id = place_booking(
        db, context.tenant_id, session_id, body.client_id, requires_plan=False
    )
    notify_booking(db, booking_id, "booked_by_studio")
    return _load(db, booking_id)


@client_router.get("/appointments/staff")
def my_staff_for_appointments(context: ClientDep) -> list[AppointmentStaff]:
    return _staff(context.session)


@client_router.get("/appointments/slots")
def my_slots(
    context: ClientDep,
    service_id: Annotated[UUID, Query()],
    day: Annotated[dt.date, Query(alias="date")],
    staff_user_id: Annotated[UUID | None, Query()] = None,
) -> list[Slot]:
    return appointment_slots(context.session, service_id, day, staff_user_id)


@client_router.post("/appointments", status_code=status.HTTP_201_CREATED)
def book_my_appointment(body: ClientAppointmentCreate, context: ClientDep) -> ClientSession:
    """The signed-in client books a free time (the business's booking rules apply)."""
    db = context.session
    ensure_may_book(db, context.tenant_id, context.client_id)
    requires_plan = db.execute(
        text("SELECT booking_requires_plan FROM app.tenants WHERE id = :id"),
        {"id": context.tenant_id},
    ).scalar_one()
    session_id = create_appointment_session(db, body.service_id, body.staff_user_id, body.starts_at)
    place_booking(db, context.tenant_id, session_id, context.client_id, requires_plan=requires_plan)
    return _load_session(db, session_id)


class AppointmentService(BaseModel):
    id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price_amount: int
    price_currency: str
    color: str | None


@client_router.get("/appointments/services")
def my_appointment_services(context: ClientDep) -> list[AppointmentService]:
    """What the client can book as a personal appointment."""
    rows = context.session.execute(
        text("""
            SELECT id, name, description, duration_minutes, price_amount, price_currency, color
            FROM app.services WHERE active AND booking_mode = 'appointment' ORDER BY name
        """)
    ).mappings()
    return [AppointmentService.model_validate(dict(r)) for r in rows]
