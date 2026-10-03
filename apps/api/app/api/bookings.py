"""Bookings: placing clients into sessions, the waitlist, check-in and cancellation.

Every change that can take or free a spot first locks the session row (`FOR UPDATE`), so
capacity checks and waitlist promotion are serialized per session."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(tags=["bookings"])

ScheduleReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]

BookingStatus = Literal["booked", "waitlisted", "checked_in", "no_show", "cancelled"]
# Statuses that hold one of the session's spots.
OCCUPYING = ("booked", "checked_in", "no_show")
OCCUPYING_SQL = "('booked', 'checked_in', 'no_show')"

# Allowed status changes by staff. Re-booking a cancelled booking is a new booking.
TRANSITIONS: dict[str, set[str]] = {
    "booked": {"checked_in", "no_show", "cancelled"},
    "checked_in": {"booked", "no_show", "cancelled"},
    "no_show": {"booked", "checked_in", "cancelled"},
    "waitlisted": {"cancelled"},
    "cancelled": set(),
}


class BookingCreate(BaseModel):
    client_id: UUID


class BookingUpdate(BaseModel):
    status: BookingStatus


class Booking(BaseModel):
    id: UUID
    session_id: UUID
    client_id: UUID
    client_name: str
    status: BookingStatus
    waitlist_position: int | None
    late_cancel: bool
    checked_in_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class ClientBooking(BaseModel):
    id: UUID
    session_id: UUID
    service_name: str
    starts_at: datetime
    ends_at: datetime
    session_status: Literal["scheduled", "cancelled"]
    status: BookingStatus
    late_cancel: bool


BOOKING_SELECT = """
    SELECT b.id, b.session_id, b.client_id,
           trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           b.status, b.late_cancel, b.checked_in_at, b.cancelled_at, b.created_at,
           CASE WHEN b.status = 'waitlisted' THEN (
               SELECT count(*) FROM app.bookings w
               WHERE w.session_id = b.session_id AND w.status = 'waitlisted'
                 AND (w.waitlisted_at, w.id) <= (b.waitlisted_at, b.id)
           ) END AS waitlist_position
    FROM app.bookings b
    JOIN app.clients c ON c.id = b.client_id
"""


def _load(db: Session, booking_id: UUID) -> Booking:
    row = (
        db.execute(text(f"{BOOKING_SELECT} WHERE b.id = :id"), {"id": booking_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Booking.model_validate(dict(row))


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def lock_session(db: Session, session_id: UUID) -> dict:
    row = (
        db.execute(
            text("""
                SELECT id, capacity, status, starts_at FROM app.sessions
                WHERE id = :id FOR UPDATE
            """),
            {"id": session_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


def _taken(db: Session, session_id: UUID) -> int:
    return db.execute(
        text(f"""
            SELECT count(*) FROM app.bookings
            WHERE session_id = :id AND status IN {OCCUPYING_SQL}
        """),
        {"id": session_id},
    ).scalar_one()


def promote_waitlist(db: Session, session_id: UUID) -> None:
    """Moves the earliest waitlisted clients into free spots of an upcoming session.
    The caller must hold the session lock (`lock_session`)."""
    db.execute(
        text(f"""
            WITH target AS (
                SELECT id, capacity FROM app.sessions
                WHERE id = :id AND status = 'scheduled' AND starts_at > now()
            ),
            free AS (
                SELECT greatest(t.capacity - (
                    SELECT count(*) FROM app.bookings
                    WHERE session_id = t.id AND status IN {OCCUPYING_SQL}
                ), 0) AS spots
                FROM target t
            ),
            next_up AS (
                SELECT b.id FROM app.bookings b
                WHERE b.session_id = :id AND b.status = 'waitlisted'
                ORDER BY b.waitlisted_at, b.id
                LIMIT (SELECT coalesce(max(spots), 0) FROM free)
            )
            UPDATE app.bookings SET status = 'booked', updated_at = now()
            WHERE id IN (SELECT id FROM next_up)
        """),
        {"id": session_id},
    )


@router.get("/sessions/{session_id}/bookings")
def list_bookings(session_id: UUID, context: ScheduleReadDep) -> list[Booking]:
    """The session's roster: live bookings first, then the waitlist in order, then history."""
    rows = context.session.execute(
        text(f"""
            {BOOKING_SELECT}
            WHERE b.session_id = :id
            ORDER BY CASE b.status WHEN 'waitlisted' THEN 1 WHEN 'cancelled' THEN 2 ELSE 0 END,
                     b.waitlisted_at NULLS FIRST, c.first_name, c.last_name, b.created_at
        """),
        {"id": session_id},
    ).mappings()
    return [Booking.model_validate(dict(row)) for row in rows]


@router.post("/sessions/{session_id}/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(session_id: UUID, body: BookingCreate, context: ManageDep) -> Booking:
    """Books the client if a spot is free, otherwise adds them to the waitlist."""
    db = context.session
    session = lock_session(db, session_id)
    if session["status"] == "cancelled":
        raise _conflict("session_cancelled")
    already = db.execute(
        text("""
            SELECT 1 FROM app.bookings
            WHERE session_id = :session_id AND client_id = :client_id AND status <> 'cancelled'
        """),
        {"session_id": session_id, "client_id": body.client_id},
    ).first()
    if already:
        raise _conflict("already_booked")

    full = _taken(db, session_id) >= session["capacity"]
    try:
        booking_id = db.execute(
            text("""
                INSERT INTO app.bookings
                    (tenant_id, session_id, client_id, status, waitlisted_at, created_by)
                VALUES (:tenant_id, :session_id, :client_id, :status,
                        CASE WHEN :full THEN now() END, app.current_user_id())
                RETURNING id
            """),
            {
                "tenant_id": context.tenant_id,
                "session_id": session_id,
                "client_id": body.client_id,
                "status": "waitlisted" if full else "booked",
                "full": full,
            },
        ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=422, detail="invalid_reference") from error
    return _load(db, booking_id)


@router.patch("/bookings/{booking_id}")
def update_booking(booking_id: UUID, body: BookingUpdate, context: ManageDep) -> Booking:
    db = context.session
    current = _load(db, booking_id)
    lock_session(db, current.session_id)
    current = _load(db, booking_id)  # re-read under the lock
    if body.status == current.status:
        return current
    if body.status not in TRANSITIONS[current.status]:
        raise _conflict("invalid_transition")

    if body.status == "cancelled":
        db.execute(
            text("""
                UPDATE app.bookings b
                SET status = 'cancelled', cancelled_at = now(), updated_at = now(),
                    late_cancel = b.status <> 'waitlisted' AND now() > s.starts_at
                        - make_interval(mins => t.cancellation_window_minutes)
                FROM app.sessions s, app.tenants t
                WHERE b.id = :id AND s.id = b.session_id AND t.id = b.tenant_id
            """),
            {"id": booking_id},
        )
        promote_waitlist(db, current.session_id)
    else:
        db.execute(
            text("""
                UPDATE app.bookings
                SET status = :status, updated_at = now(),
                    checked_in_at = CASE WHEN :status = 'checked_in' THEN now() END
                WHERE id = :id
            """),
            {"id": booking_id, "status": body.status},
        )
    return _load(db, booking_id)


@router.get("/clients/{client_id}/bookings")
def list_client_bookings(client_id: UUID, context: ClientsReadDep) -> list[ClientBooking]:
    """A client's bookings, newest session first."""
    rows = context.session.execute(
        text("""
            SELECT b.id, b.session_id, sv.name AS service_name, s.starts_at, s.ends_at,
                   s.status AS session_status, b.status, b.late_cancel
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = :id
            ORDER BY s.starts_at DESC
            LIMIT 200
        """),
        {"id": client_id},
    ).mappings()
    return [ClientBooking.model_validate(dict(row)) for row in rows]
