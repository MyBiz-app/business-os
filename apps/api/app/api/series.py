"""Booking series (slice C5): a standing weekly booking of a court or a private appointment, or
a course joined with one sign-up.

The series is the client's wish; each date becomes an ordinary session and booking (so the
calendar, the roster and the reports need no change) and the booking remembers its series. Dates
that cannot be booked (the court is taken, the coach is off) are skipped and listed in the answer,
the rest are kept. Cancelling a series cancels what is still ahead, under the usual cancellation
rules of each booking."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.appointments import create_appointment_session
from app.api.bookings import (
    _check_session_branch,
    _load,
    cancel_booking,
    lock_session,
    place_booking,
)
from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.api.health import ensure_may_book
from app.api.pagination import PageDep
from app.api.resources import ReservationFields, create_resource_session
from app.core.permissions import Permission
from app.messaging.notifications import notify_booking
from app.schedule.series import occurrence_starts

router = APIRouter(tags=["series"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]

Kind = Literal["resource", "appointment", "class"]


class SeriesFields(BaseModel):
    kind: Kind = Field(
        description="resource: a court or room at the same time each week; appointment: a private"
        " lesson or treatment with the same staff member; class: a course, joined once"
    )
    service_id: UUID
    starts_at: datetime = Field(description="The first date; the others follow every N weeks")
    every_weeks: int = Field(default=1, ge=1, le=4)
    occurrences: int = Field(ge=2, le=52, description="How many dates, the first included")
    room_id: UUID | None = Field(default=None, description="resource: which court or room")
    minutes: int | None = Field(default=None, ge=15, le=1440, description="resource: how long")
    staff_user_id: UUID | None = Field(default=None, description="appointment: with whom")
    dependent_id: UUID | None = None

    @model_validator(mode="after")
    def needs_by_kind(self) -> "SeriesFields":
        if self.kind == "resource" and (self.room_id is None or self.minutes is None):
            raise ValueError("a resource series needs room_id and minutes")
        if self.kind == "appointment" and self.staff_user_id is None:
            raise ValueError("an appointment series needs staff_user_id")
        return self


class SeriesCreate(SeriesFields):
    client_id: UUID


class Series(BaseModel):
    id: UUID
    client_id: UUID
    kind: Kind
    service_id: UUID
    service_name: str
    room_id: UUID | None
    staff_user_id: UUID | None
    first_starts_at: datetime
    minutes: int | None
    every_weeks: int
    occurrences: int
    status: Literal["active", "cancelled"]
    upcoming: int = Field(description="Dates still ahead with a live booking")


class SeriesOccurrence(BaseModel):
    starts_at: datetime
    outcome: Literal["booked", "waitlisted", "skipped"]
    reason: str | None = Field(default=None, description="Why a date was skipped")
    booking_id: UUID | None = None


class SeriesCreated(Series):
    results: list[SeriesOccurrence]


SELECT = """
    SELECT ss.id, ss.client_id, ss.kind, ss.service_id, sv.name AS service_name, ss.room_id,
           ss.staff_user_id, ss.first_starts_at, ss.minutes, ss.every_weeks, ss.occurrences,
           ss.status,
           (SELECT count(*) FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
            WHERE b.series_id = ss.id AND b.status IN ('booked', 'waitlisted')
              AND s.starts_at > now())::int AS upcoming
    FROM app.booking_series ss JOIN app.services sv ON sv.id = ss.service_id
"""


def _load_series(db: Session, series_id: UUID) -> Series:
    row = db.execute(text(SELECT + " WHERE ss.id = :id"), {"id": series_id}).mappings().first()
    if row is None:
        raise not_found()
    return Series.model_validate(dict(row))


def _class_session(db: Session, service_id: UUID, starts_at: datetime) -> UUID:
    found = db.execute(
        text("""
            SELECT id FROM app.sessions
            WHERE service_id = :service AND starts_at = :starts AND status = 'scheduled'
            ORDER BY created_at LIMIT 1
        """),
        {"service": service_id, "starts": starts_at},
    ).first()
    if found is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_session")
    return found.id


def _session_for(
    db: Session, body: SeriesFields, starts_at: datetime, context: TenantContext | None
) -> UUID:
    if body.kind == "resource":
        assert body.room_id is not None and body.minutes is not None
        return create_resource_session(
            db,
            ReservationFields(
                service_id=body.service_id,
                room_id=body.room_id,
                starts_at=starts_at,
                minutes=body.minutes,
            ),
        )
    if body.kind == "appointment":
        assert body.staff_user_id is not None
        return create_appointment_session(db, body.service_id, body.staff_user_id, starts_at)
    session_id = _class_session(db, body.service_id, starts_at)
    if context is not None:
        _check_session_branch(context, session_id)
    return session_id


def create_series(
    db: Session,
    tenant_id: UUID,
    client_id: UUID,
    body: SeriesFields,
    *,
    requires_plan: bool,
    context: TenantContext | None = None,
    notify: bool = False,
) -> SeriesCreated:
    if body.starts_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_started")
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = :id"), {"id": tenant_id}
    ).scalar_one()
    series_id = db.execute(
        text("""
            INSERT INTO app.booking_series
                (tenant_id, client_id, kind, service_id, room_id, staff_user_id, dependent_id,
                 first_starts_at, minutes, every_weeks, occurrences, created_by)
            VALUES (:tenant, :client, :kind, :service, :room, :staff, :dependent, :first, :minutes,
                    :every, :count, app.current_user_id())
            RETURNING id
        """),
        {
            "tenant": tenant_id,
            "client": client_id,
            "kind": body.kind,
            "service": body.service_id,
            "room": body.room_id,
            "staff": body.staff_user_id,
            "dependent": body.dependent_id,
            "first": body.starts_at,
            "minutes": body.minutes,
            "every": body.every_weeks,
            "count": body.occurrences,
        },
    ).scalar_one()

    results: list[SeriesOccurrence] = []
    notified = False
    for starts_at in occurrence_starts(
        body.starts_at, body.every_weeks, body.occurrences, time_zone
    ):
        try:
            with db.begin_nested():  # a date that fails leaves nothing behind
                session_id = _session_for(db, body, starts_at, context)
                booking_id = place_booking(
                    db,
                    tenant_id,
                    session_id,
                    client_id,
                    requires_plan=requires_plan,
                    dependent_id=body.dependent_id,
                )
                db.execute(
                    text("UPDATE app.bookings SET series_id = :series WHERE id = :id"),
                    {"series": series_id, "id": booking_id},
                )
        except HTTPException as error:
            results.append(
                SeriesOccurrence(starts_at=starts_at, outcome="skipped", reason=str(error.detail))
            )
            continue
        booking = _load(db, booking_id)
        results.append(
            SeriesOccurrence(
                starts_at=starts_at,
                outcome="waitlisted" if booking.status == "waitlisted" else "booked",
                booking_id=booking_id,
            )
        )
        if notify and not notified:  # one message for the series, not one per date
            notify_booking(db, booking_id, "booked_by_studio")
            notified = True

    if all(r.outcome == "skipped" for r in results):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_date_available")
    return SeriesCreated(**_load_series(db, series_id).model_dump(), results=results)


def cancel_series(db: Session, series_id: UUID, context: TenantContext | None = None) -> Series:
    """Cancels the dates still ahead; what already happened stays as it was."""
    current = _load_series(db, series_id)
    if current.status == "cancelled":
        return current
    rows = db.execute(
        text("""
            SELECT b.id, b.session_id FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
            WHERE b.series_id = :id AND b.status IN ('booked', 'waitlisted') AND s.starts_at > now()
            ORDER BY s.starts_at
        """),
        {"id": series_id},
    ).all()
    for row in rows:
        if context is not None:
            _check_session_branch(context, row.session_id)
        lock_session(db, row.session_id)
        cancel_booking(db, row.id, row.session_id)
    db.execute(
        text("""
            UPDATE app.booking_series
            SET status = 'cancelled', cancelled_at = now(), updated_at = now() WHERE id = :id
        """),
        {"id": series_id},
    )
    return _load_series(db, series_id)


# --- Staff ------------------------------------------------------------------------------------


@router.post("/series", status_code=status.HTTP_201_CREATED)
def book_standing_series(body: SeriesCreate, context: ManageDep) -> SeriesCreated:
    """Books a client into a standing booking or a course (staff may book without a plan)."""
    return create_series(
        context.session,
        context.tenant_id,
        body.client_id,
        body,
        requires_plan=False,
        context=context,
        notify=True,
    )


@router.get("/clients/{client_id}/series")
def list_client_booking_series(client_id: UUID, context: ReadDep, page: PageDep) -> list[Series]:
    rows = (
        context.session.execute(
            text(
                SELECT + " WHERE ss.client_id = :client ORDER BY ss.created_at DESC, ss.id "
                "LIMIT :limit OFFSET :offset"
            ),
            {"client": client_id, "limit": page.limit, "offset": page.offset},
        )
        .mappings()
        .all()
    )
    return [Series.model_validate(dict(row)) for row in rows]


@router.get("/series/{series_id}")
def get_booking_series(series_id: UUID, context: ReadDep) -> Series:
    return _load_series(context.session, series_id)


@router.post("/series/{series_id}/cancel")
def cancel_booking_series(series_id: UUID, context: ManageDep) -> Series:
    return cancel_series(context.session, series_id, context)


# --- Client -----------------------------------------------------------------------------------


@client_router.post("/series", status_code=status.HTTP_201_CREATED)
def book_my_booking_series(body: SeriesFields, context: ClientDep) -> SeriesCreated:
    """The signed-in client sets up a standing booking (the business's booking rules apply).
    A business paid in the app takes each court payment separately, so a series there is made
    by the business."""
    db = context.session
    ensure_may_book(db, context.tenant_id, context.client_id)
    row = db.execute(
        text("SELECT booking_requires_plan, resource_payment FROM app.tenants WHERE id = :id"),
        {"id": context.tenant_id},
    ).one()
    if body.kind == "resource" and row.resource_payment == "app":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="series_needs_staff")
    return create_series(
        db,
        context.tenant_id,
        context.client_id,
        body,
        requires_plan=row.booking_requires_plan and body.kind != "resource",
    )


@client_router.get("/series")
def my_booking_series(context: ClientDep, page: PageDep) -> list[Series]:
    rows = (
        context.session.execute(
            text(
                SELECT + " WHERE ss.client_id = :client ORDER BY ss.created_at DESC, ss.id "
                "LIMIT :limit OFFSET :offset"
            ),
            {"client": context.client_id, "limit": page.limit, "offset": page.offset},
        )
        .mappings()
        .all()
    )
    return [Series.model_validate(dict(row)) for row in rows]


@client_router.post("/series/{series_id}/cancel")
def cancel_my_booking_series(series_id: UUID, context: ClientDep) -> Series:
    return cancel_series(context.session, series_id)
