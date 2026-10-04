"""Bookings: placing clients into sessions, the waitlist, check-in and cancellation.

Every change that can take or free a spot first locks the session row (`FOR UPDATE`), so
capacity checks and waitlist promotion are serialized per session."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.api.health import HEALTH_STATE_SQL, HealthState
from app.api.plans import usable_entitlement
from app.permissions import Permission

router = APIRouter(tags=["bookings"])

ScheduleReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]

BookingStatus = Literal["booked", "waitlisted", "checked_in", "no_show", "cancelled"]

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
    plan_name: str | None = Field(description="The client's plan this booking uses, if any")
    status: BookingStatus
    waitlist_position: int | None
    late_cancel: bool
    checked_in_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    health_state: HealthState = Field(description="The client's health declaration state")


class ClientBooking(BaseModel):
    id: UUID
    session_id: UUID
    service_name: str
    starts_at: datetime
    ends_at: datetime
    session_status: Literal["scheduled", "cancelled"]
    status: BookingStatus
    late_cancel: bool


BOOKING_SELECT = f"""
    SELECT b.id, b.session_id, b.client_id,
           trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           e.name AS plan_name,
           b.status, b.late_cancel, b.checked_in_at, b.cancelled_at, b.created_at,
           app.waitlist_position(b.id) AS waitlist_position,
           {HEALTH_STATE_SQL} AS health_state
    FROM app.bookings b
    JOIN app.clients c ON c.id = b.client_id
    JOIN app.tenants t ON t.id = b.tenant_id
    LEFT JOIN app.entitlements e ON e.id = b.entitlement_id
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
    """Locks the session row for this transaction (capacity checks, waitlist promotion)."""
    row = (
        db.execute(
            text("SELECT * FROM app.lock_session(:id)"),
            {"id": session_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


def session_counts(db: Session, session_id: UUID) -> tuple[int, int]:
    """(booked, waitlisted) across all clients, even when the caller is a client."""
    booked, waitlisted = db.execute(
        text("SELECT booked, waitlisted FROM app.session_counts(:id)"), {"id": session_id}
    ).one()
    return booked, waitlisted


def promote_waitlist(db: Session, session_id: UUID) -> None:
    """Moves the earliest waitlisted clients into free spots of an upcoming session.
    The caller must hold the session lock (`lock_session`)."""
    db.execute(text("SELECT app.promote_waitlist(:id)"), {"id": session_id})


def place_booking(
    db: Session, tenant_id: UUID, session_id: UUID, client_id: UUID, *, requires_plan: bool
) -> UUID:
    """Books the client if a spot is free, otherwise adds them to the waitlist. The booking
    uses one of the client's plans when one is valid; with `requires_plan`, it must."""
    session = lock_session(db, session_id)
    if session["status"] == "cancelled":
        raise _conflict("session_cancelled")
    already = db.execute(
        text("""
            SELECT 1 FROM app.bookings
            WHERE session_id = :session_id AND client_id = :client_id AND status <> 'cancelled'
        """),
        {"session_id": session_id, "client_id": client_id},
    ).first()
    if already:
        raise _conflict("already_booked")

    entitlement_id = usable_entitlement(db, client_id, session_id)
    if entitlement_id is None and requires_plan:
        raise _conflict("no_valid_plan")

    booked, _ = session_counts(db, session_id)
    full = booked >= session["capacity"]
    try:
        return db.execute(
            text("""
                INSERT INTO app.bookings
                    (tenant_id, session_id, client_id, entitlement_id, status, waitlisted_at,
                     created_by)
                VALUES (:tenant_id, :session_id, :client_id, :entitlement_id, :status,
                        CASE WHEN :full THEN now() END, app.current_user_id())
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "client_id": client_id,
                "entitlement_id": entitlement_id,
                "status": "waitlisted" if full else "booked",
                "full": full,
            },
        ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=422, detail="invalid_reference") from error


def cancel_booking(db: Session, booking_id: UUID, session_id: UUID) -> None:
    """Cancels a booking (late if inside the business's window) and fills the freed spot."""
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
    promote_waitlist(db, session_id)


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
    # Staff may book without a plan (walk-ins pay at the desk); the roster shows it.
    booking_id = place_booking(
        context.session, context.tenant_id, session_id, body.client_id, requires_plan=False
    )
    return _load(context.session, booking_id)


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
        cancel_booking(db, booking_id, current.session_id)
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
