"""Bookings: placing clients into sessions, the waitlist, check-in and cancellation.

Every change that can take or free a spot first locks the session row (`FOR UPDATE`), so
capacity checks and waitlist promotion are serialized per session."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import ensure_not_erased, not_found
from app.api.deps import TenantContext, ensure_branch_allowed, ensure_branch_visible, require
from app.api.health import HEALTH_STATE_SQL, HealthState
from app.api.pagination import NEXT_CURSOR_HEADER, KeysetDep, WidePageDep, encode_cursor
from app.api.plans import quota_reached, usable_entitlement
from app.catalog.verticals import CATALOG, VerticalPack
from app.core import events
from app.core.permissions import Permission
from app.messaging.notifications import notify_booking
from app.schedule.waitlist import mode_for, spot_opened, spot_taken

router = APIRouter(tags=["bookings"])

ScheduleReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]

# Who may add a client to a full class: owners, managers and branch managers (not front desk or
# instructors). Clients never can.
OVER_CAPACITY_ROLES = frozenset({"owner", "manager", "branch_manager"})

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
    dependent_id: UUID | None = Field(
        default=None, description="Which of the client's pets / children comes (#43)"
    )
    over_capacity: bool = Field(
        default=False,
        description="Book the client even though the class is full (owners and managers only); "
        "ignored while a spot is free",
    )


class EntryCreate(BaseModel):
    client_id: UUID
    service_id: UUID = Field(description="An open-entry service (open gym, pool, co-working)")
    location_id: UUID | None = Field(
        default=None, description="The branch the client walks into; needed when several are open"
    )
    without_plan: bool = Field(
        default=False, description="Let the client in without a valid plan (pays at the desk)"
    )


class BookingUpdate(BaseModel):
    status: BookingStatus


class Booking(BaseModel):
    id: UUID
    session_id: UUID
    client_id: UUID
    client_name: str
    dependent_id: UUID | None = None
    dependent_name: str | None = Field(default=None, description="The pet / child who comes")
    plan_name: str | None = Field(description="The client's plan this booking uses, if any")
    status: BookingStatus
    waitlist_position: int | None
    over_capacity: bool = Field(description="Added beyond the class's capacity by a manager")
    over_capacity_at: datetime | None = None
    late_cancel: bool
    credit_released: bool = Field(
        description="The visit is not used up: the policy only records the late cancellation or "
        "no-show, or a manager gave it back"
    )
    waived_at: datetime | None = Field(description="When a manager gave the visit back")
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
    dependent_name: str | None = None
    rating: int | None = Field(default=None, description="The client's review of the visit")
    free_cancel_until: datetime | None = Field(
        default=None, description="Upcoming bookings: cancelling before this moment is free"
    )


NO_DEPENDENT = "'00000000-0000-0000-0000-000000000000'::uuid"

BOOKING_SELECT = f"""
    SELECT b.id, b.session_id, b.client_id,
           trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           b.dependent_id, d.name AS dependent_name,
           e.name AS plan_name,
           b.status, b.over_capacity, b.over_capacity_at, b.late_cancel, b.credit_released,
           b.waived_at, b.checked_in_at,
           b.cancelled_at, b.created_at,
           app.waitlist_position(b.id) AS waitlist_position,
           {HEALTH_STATE_SQL} AS health_state
    FROM app.bookings b
    JOIN app.clients c ON c.id = b.client_id
    JOIN app.tenants t ON t.id = b.tenant_id
    LEFT JOIN app.entitlements e ON e.id = b.entitlement_id
    LEFT JOIN app.dependents d ON d.id = b.dependent_id
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


def _check_session_branch(context: TenantContext, session_id: UUID) -> None:
    """A member kept to some branches only reaches the sessions (and so the rosters) of theirs."""
    if context.branches is None:
        return
    row = context.session.execute(
        text("SELECT location_id FROM app.sessions WHERE id = :id"), {"id": session_id}
    ).first()
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row.location_id)


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
    spot_opened(db, session_id)  # whoever is still waiting hears about a spot that stays free


def place_booking(
    db: Session,
    tenant_id: UUID,
    session_id: UUID,
    client_id: UUID,
    *,
    requires_plan: bool,
    dependent_id: UUID | None = None,
    over_capacity: bool = False,
) -> UUID:
    """Books the client if a spot is free, otherwise adds them to the waitlist (or, with
    `over_capacity`, books them beyond the capacity and marks the booking). The booking
    uses one of the client's plans when one is valid; with `requires_plan`, it must. A booking
    can be for one of the client's dependents (a pet, a child); a client can then hold one
    booking per session and dependent."""
    ensure_not_erased(db, client_id)
    ensure_dependent(db, tenant_id, client_id, dependent_id)
    session = lock_session(db, session_id)
    if session["status"] == "cancelled":
        raise _conflict("session_cancelled")
    already = db.execute(
        text(f"""
            SELECT 1 FROM app.bookings
            WHERE session_id = :session_id AND client_id = :client_id AND status <> 'cancelled'
              AND coalesce(dependent_id, {NO_DEPENDENT}) = coalesce(:dependent_id, {NO_DEPENDENT})
        """),
        {"session_id": session_id, "client_id": client_id, "dependent_id": dependent_id},
    ).first()
    if already:
        raise _conflict("already_booked")

    entitlement_id = usable_entitlement(db, client_id, session_id)
    if entitlement_id is None and requires_plan:
        raise _conflict(
            "period_quota_reached" if quota_reached(db, client_id, session_id) else "no_valid_plan"
        )

    booked, _ = session_counts(db, session_id)
    full = booked >= session["capacity"]
    over = full and over_capacity
    if full and not over:
        service_id = db.execute(
            text("SELECT service_id FROM app.sessions WHERE id = :id"), {"id": session_id}
        ).scalar_one()
        if mode_for(db, service_id) == "off":
            raise _conflict("session_full")  # the business does not keep a waitlist
    try:
        booking_id = db.execute(
            text("""
                INSERT INTO app.bookings
                    (tenant_id, session_id, client_id, dependent_id, entitlement_id, status,
                     waitlisted_at, created_by, over_capacity, over_capacity_by, over_capacity_at)
                VALUES (:tenant_id, :session_id, :client_id, :dependent_id, :entitlement_id,
                        :status, CASE WHEN :waitlist THEN now() END, app.current_user_id(),
                        :over, CASE WHEN :over THEN app.current_user_id() END,
                        CASE WHEN :over THEN now() END)
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "client_id": client_id,
                "dependent_id": dependent_id,
                "entitlement_id": entitlement_id,
                "status": "waitlisted" if full and not over else "booked",
                "waitlist": full and not over,
                "over": over,
            },
        ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=422, detail="invalid_reference") from error
    if not (full and not over):
        spot_taken(db, session_id, client_id)
    events.record(db, "first_booking", once=True)
    return booking_id


def ensure_dependent(
    db: Session, tenant_id: UUID, client_id: UUID, dependent_id: UUID | None
) -> None:
    """The dependent must be the client's and active; businesses whose pack says every visit
    is for a dependent (a groomer: which dog?) require one."""
    if dependent_id is None:
        if tenant_pack(db, tenant_id).dependent_required:
            raise HTTPException(status_code=422, detail="dependent_required")
        return
    found = db.execute(
        text("""
            SELECT 1 FROM app.dependents
            WHERE id = :id AND client_id = :client_id AND active
        """),
        {"id": dependent_id, "client_id": client_id},
    ).first()
    if found is None:
        raise HTTPException(status_code=422, detail="unknown_dependent")


def tenant_pack(db: Session, tenant_id: UUID) -> VerticalPack:
    vertical = db.execute(
        text("SELECT vertical FROM app.tenants WHERE id = :id"), {"id": tenant_id}
    ).scalar_one()
    return CATALOG[vertical]


WAITLIST_GRACE_MINUTES = 30  # a client signed in from the waitlist may still cancel for free


def cancel_booking(db: Session, booking_id: UUID, session_id: UUID) -> None:
    """Cancels a booking and fills the freed spot. Inside the policy's window it is a late
    cancellation, which the policy may count as a used visit or only record.

    A client who was signed in automatically from the waitlist (the booking carries its
    `waitlisted_at` and was last changed when the spot opened) cancels without penalty in the
    first `WAITLIST_GRACE_MINUTES`, since they did not choose the time themselves."""
    db.execute(
        text("""
            WITH terms AS (
                SELECT b.id, ct.late_outcome,
                       b.status <> 'waitlisted'
                           AND now() > s.starts_at - make_interval(mins => ct.free_minutes)
                           AND NOT (b.status = 'booked' AND b.waitlisted_at IS NOT NULL
                                    AND b.updated_at > now() - make_interval(mins => :grace))
                       AS late
                FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id
                CROSS JOIN LATERAL app.cancellation_terms(b.session_id, b.entitlement_id) ct
                WHERE b.id = :id
            )
            UPDATE app.bookings b
            SET status = 'cancelled', cancelled_at = now(), updated_at = now(),
                late_cancel = terms.late,
                credit_released = terms.late AND terms.late_outcome <> 'counts'
            FROM terms
            WHERE b.id = terms.id
        """),
        {"id": booking_id, "grace": WAITLIST_GRACE_MINUTES},
    )
    promote_waitlist(db, session_id)


def settle_no_show(db: Session, booking_id: UUID, no_show: bool) -> None:
    """A client marked as not having come uses the visit up or not, as the policy says; moving
    the booking out of no-show undoes that (a give-back by a manager is kept only for the
    no-show it was given for)."""
    db.execute(
        text("""
            UPDATE app.bookings b
            SET credit_released = CASE WHEN :no_show THEN ct.no_show_outcome <> 'counts'
                                       ELSE false END,
                waived_by = CASE WHEN :no_show THEN b.waived_by END,
                waived_at = CASE WHEN :no_show THEN b.waived_at END,
                waive_reason = CASE WHEN :no_show THEN b.waive_reason END
            FROM app.bookings x
            CROSS JOIN LATERAL app.cancellation_terms(x.session_id, x.entitlement_id) ct
            WHERE b.id = :id AND x.id = b.id
              AND NOT (:no_show AND b.waived_at IS NOT NULL)
        """),
        {"id": booking_id, "no_show": no_show},
    )


@router.get("/sessions/{session_id}/bookings")
def list_bookings(session_id: UUID, context: ScheduleReadDep, page: WidePageDep) -> list[Booking]:
    """The session's roster: live bookings first, then the waitlist in order, then history."""
    _check_session_branch(context, session_id)
    rows = context.session.execute(
        text(f"""
            {BOOKING_SELECT}
            WHERE b.session_id = :id
            ORDER BY CASE b.status WHEN 'waitlisted' THEN 1 WHEN 'cancelled' THEN 2 ELSE 0 END,
                     b.waitlisted_at NULLS FIRST, c.first_name, c.last_name, b.created_at, b.id
            LIMIT :limit OFFSET :offset
        """),
        {"id": session_id, "limit": page.limit, "offset": page.offset},
    ).mappings()
    return [Booking.model_validate(dict(row)) for row in rows]


@router.post("/sessions/{session_id}/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(session_id: UUID, body: BookingCreate, context: ManageDep) -> Booking:
    """Books the client if a spot is free, otherwise adds them to the waitlist."""
    _check_session_branch(context, session_id)
    if body.over_capacity and context.role not in OVER_CAPACITY_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    # Staff may book without a plan (walk-ins pay at the desk); the roster shows it.
    booking_id = place_booking(
        context.session,
        context.tenant_id,
        session_id,
        body.client_id,
        requires_plan=False,
        dependent_id=body.dependent_id,
        over_capacity=body.over_capacity,
    )
    notify_booking(context.session, booking_id, "booked_by_studio")
    return _load(context.session, booking_id)


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def check_in_entry(body: EntryCreate, context: ManageDep) -> Booking:
    """A client walks into an open-entry place: the visit is booked in the opening hours that
    are on now and checked in at once. It uses one of the client's plans; without a valid plan
    the desk must say `without_plan`."""
    db = context.session
    ensure_branch_allowed(context, body.location_id)
    rows = (
        db.execute(
            text("""
                SELECT s.id, s.location_id
                FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
                WHERE s.service_id = :service_id AND sv.open_entry AND sv.active
                  AND s.status = 'scheduled' AND s.starts_at <= now() AND s.ends_at > now()
                  AND (CAST(:location_id AS uuid) IS NULL OR s.location_id = :location_id)
                  AND (s.location_id IS NULL OR app.in_branch(s.location_id))
                ORDER BY s.starts_at
            """),
            {"service_id": body.service_id, "location_id": body.location_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        raise _conflict("entry_closed")
    if len(rows) > 1 and body.location_id is None:
        raise HTTPException(status_code=422, detail="location_required")
    session_id = rows[0]["id"]
    booking_id = place_booking(
        db,
        context.tenant_id,
        session_id,
        body.client_id,
        requires_plan=not body.without_plan,
    )
    booked = db.execute(
        text("""
            UPDATE app.bookings
            SET status = 'checked_in', checked_in_at = now(), updated_at = now()
            WHERE id = :id AND status = 'booked'
        """),
        {"id": booking_id},
    ).rowcount
    if not booked:  # the place is full: no waitlist for walking in
        raise _conflict("session_full")
    return _load(db, booking_id)


@router.patch("/bookings/{booking_id}")
def update_booking(booking_id: UUID, body: BookingUpdate, context: ManageDep) -> Booking:
    db = context.session
    current = _load(db, booking_id)
    _check_session_branch(context, current.session_id)
    lock_session(db, current.session_id)
    current = _load(db, booking_id)  # re-read under the lock
    if body.status == current.status:
        return current
    if body.status not in TRANSITIONS[current.status]:
        raise _conflict("invalid_transition")

    if body.status == "cancelled":
        cancel_booking(db, booking_id, current.session_id)
        notify_booking(db, booking_id, "booking_cancelled_by_studio")
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
        if body.status == "no_show" or current.status == "no_show":
            settle_no_show(db, booking_id, body.status == "no_show")
    return _load(db, booking_id)


@router.get("/clients/{client_id}/bookings")
def list_client_bookings(
    client_id: UUID, context: ClientsReadDep, page: KeysetDep, response: Response
) -> list[ClientBooking]:
    """A client's bookings, newest session first (a member kept to some branches sees those
    made at their branches). The header `X-Next-Cursor`, when present, goes in `after`."""
    rows = (
        context.session.execute(
            text("""
            SELECT b.id, b.session_id, sv.name AS service_name, s.starts_at, s.ends_at,
                   s.status AS session_status, b.status, b.late_cancel,
                   d.name AS dependent_name,
                   (SELECT r.rating FROM app.reviews r WHERE r.booking_id = b.id) AS rating,
                   b.id AS key_id
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            LEFT JOIN app.dependents d ON d.id = b.dependent_id
            WHERE b.client_id = :id AND (s.location_id IS NULL OR app.in_branch(s.location_id))
              AND (CAST(:after_at AS timestamptz) IS NULL
                   OR (s.starts_at, b.id) <
                       (CAST(:after_at AS timestamptz), CAST(:after_id AS uuid)))
            ORDER BY s.starts_at DESC, b.id DESC
            LIMIT :fetch OFFSET :offset
        """),
            {
                "id": client_id,
                "fetch": page.fetch,
                "offset": page.offset,
                "after_at": page.after[0] if page.after else None,
                "after_id": page.after[1] if page.after and len(page.after) > 1 else None,
            },
        )
        .mappings()
        .all()
    )
    if len(rows) > page.limit:
        rows = rows[: page.limit]
        response.headers[NEXT_CURSOR_HEADER] = encode_cursor(
            rows[-1]["starts_at"].isoformat(), rows[-1]["key_id"]
        )
    return [ClientBooking.model_validate(dict(row)) for row in rows]
