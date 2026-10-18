"""The smart waitlist (round 7, R30; migration 0132).

A client waits for a given time, a range of hours or a whole day of a class, an appointment or a
court. When a spot opens, the business's mode decides what happens (see app/schedule/waitlist.py):
`auto` signs the first one in (classes, until a few hours before), `first_come` tells everyone
waiting and the first to take it gets it, `manual` leaves it to the team. Taking a spot goes
through the normal booking path (plan, health declaration, one booking per session), so two people
tapping together never get the same spot."""

import datetime as dt
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.appointments import create_appointment_session
from app.api.bookings import lock_session, place_booking
from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, ensure_branch_visible, require
from app.api.health import ensure_may_book
from app.api.resources import ReservationFields, _payment, create_resource_session
from app.core.permissions import Permission
from app.messaging.notifications import notify_booking
from app.schedule.waitlist import (
    MAX_ACTIVE_REQUESTS,
    mode_for,
    request_expiry,
    spot_taken,
)

router = APIRouter(tags=["waitlist"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.BOOKINGS_MANAGE))]

EntryKind = Literal["session", "slot", "range", "day"]


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# --- Taking a spot -----------------------------------------------------------------------------


def take_spot(
    db: Session,
    tenant_id: UUID,
    session_id: UUID,
    client_id: UUID,
    *,
    requires_plan: bool,
) -> tuple[UUID, UUID]:
    """Books the client into the spot that opened in `session_id`: the class itself, or, for a
    personal appointment or a court, a new session at the same time (the freed one stays as it
    was). Returns (session, booking). 409 `spot_taken` when someone was faster."""
    lock_session(db, session_id)
    spot = (
        db.execute(
            text("""
                SELECT s.service_id, s.starts_at, s.ends_at, s.room_id, s.instructor_user_id,
                       sv.booking_mode
                FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
                WHERE s.id = :id
            """),
            {"id": session_id},
        )
        .mappings()
        .first()
    )
    if spot is None:
        raise not_found()
    if not db.execute(text("SELECT app.waitlist_slot_is_free(:id)"), {"id": session_id}).scalar():
        raise _conflict("spot_taken")
    target = session_id
    if spot["booking_mode"] == "class":
        waiting = db.execute(
            text("""
                SELECT id FROM app.bookings
                WHERE session_id = :s AND client_id = :c AND status = 'waitlisted'
            """),
            {"s": session_id, "c": client_id},
        ).scalar()
        if waiting is not None:  # already on the class's own list: that place becomes a booking
            db.execute(
                text("UPDATE app.bookings SET status = 'booked', updated_at = now() WHERE id = :b"),
                {"b": waiting},
            )
            spot_taken(db, session_id, client_id)
            return session_id, waiting
    elif spot["booking_mode"] == "appointment":
        target = create_appointment_session(
            db, spot["service_id"], spot["instructor_user_id"], spot["starts_at"]
        )
    else:
        minutes = int((spot["ends_at"] - spot["starts_at"]).total_seconds() // 60)
        target = create_resource_session(
            db,
            ReservationFields(
                service_id=spot["service_id"],
                room_id=spot["room_id"],
                starts_at=spot["starts_at"],
                minutes=minutes,
            ),
        )
    booking_id = place_booking(db, tenant_id, target, client_id, requires_plan=requires_plan)
    return target, booking_id


# --- The team's screen -------------------------------------------------------------------------

# One row per waiting client: a request (range, day or exact time) or a place on a class's own
# list. `open_*` is a spot that is free right now for them, which is what the team acts on in the
# manual mode.
ENTRIES_SQL = """
    WITH entries AS (
        SELECT r.id, 'request' AS source, r.client_id, r.service_id, r.kind,
               NULL::uuid AS session_id, r.day, r.from_time, r.to_time, r.starts_at,
               r.location_id, r.staff_user_id,
               r.status, r.created_at,
               row_number() OVER (PARTITION BY r.service_id, r.day
                                  ORDER BY r.created_at, r.id)::int AS position,
               (SELECT s.id FROM app.sessions s
                WHERE s.tenant_id = r.tenant_id AND s.service_id = r.service_id
                  AND s.starts_at > now() AND r.expires_at > now()
                  AND s.starts_at >= r.day::timestamptz - interval '1 day'
                  AND s.starts_at < r.day::timestamptz + interval '2 days'
                  AND app.waitlist_matches(r.id, s.id) AND app.waitlist_slot_is_free(s.id)
                ORDER BY s.starts_at LIMIT 1) AS open_session_id
        FROM app.waitlist_requests r
        WHERE r.status IN ('active', 'offered') AND r.expires_at > now()
        UNION ALL
        SELECT b.id, 'booking', b.client_id, s.service_id, 'session', s.id,
               (s.starts_at AT TIME ZONE t.time_zone)::date, NULL, NULL, s.starts_at,
               s.location_id, s.instructor_user_id, 'active', b.waitlisted_at,
               app.waitlist_position(b.id),
               CASE WHEN app.waitlist_slot_is_free(s.id) THEN s.id END
        FROM app.bookings b
        JOIN app.sessions s ON s.id = b.session_id
        JOIN app.tenants t ON t.id = b.tenant_id
        WHERE b.status = 'waitlisted' AND s.status = 'scheduled' AND s.starts_at > now()
    )
    SELECT e.id, e.source, e.client_id, trim(c.first_name || ' ' || coalesce(c.last_name, ''))
               AS client_name,
           e.service_id, sv.name AS service_name, e.kind, e.session_id, e.day, e.from_time,
           e.to_time, e.starts_at, e.location_id, l.name AS location_name,
           e.staff_user_id, st.name AS staff_name, e.position, e.created_at,
           app.waitlist_mode_for(e.service_id) AS mode,
           CASE WHEN offer.status = 'open' THEN 'offered' ELSE 'waiting' END AS status,
           e.open_session_id, os.starts_at AS open_starts_at
    FROM entries e
    JOIN app.clients c ON c.id = e.client_id
    JOIN app.services sv ON sv.id = e.service_id
    LEFT JOIN app.locations l ON l.id = e.location_id
    LEFT JOIN app.appointment_staff() st ON st.user_id = e.staff_user_id
    LEFT JOIN app.sessions os ON os.id = e.open_session_id
    LEFT JOIN app.waitlist_offers offer
        ON offer.session_id = e.open_session_id AND offer.client_id = e.client_id
    WHERE (e.location_id IS NULL OR app.in_branch(e.location_id))
      AND (CAST(:day AS date) IS NULL OR e.day = CAST(:day AS date))
      AND (CAST(:location AS uuid) IS NULL OR e.location_id = CAST(:location AS uuid))
      AND (CAST(:service AS uuid) IS NULL OR e.service_id = CAST(:service AS uuid))
      AND (CAST(:mode AS text) IS NULL OR app.waitlist_mode_for(e.service_id) = CAST(:mode AS text))
    ORDER BY e.day, sv.name, e.position, e.id
    LIMIT 300
"""


class WaitlistEntry(BaseModel):
    id: UUID
    source: Literal["request", "booking"] = Field(
        description="request: a time range, day or exact time; booking: a place on a class's list"
    )
    client_id: UUID
    client_name: str
    service_id: UUID
    service_name: str
    kind: EntryKind
    session_id: UUID | None = Field(default=None, description="The class, for a booking entry")
    day: dt.date
    from_time: dt.time | None = None
    to_time: dt.time | None = None
    starts_at: datetime | None = None
    location_id: UUID | None = None
    location_name: str | None = None
    staff_user_id: UUID | None = None
    staff_name: str | None = None
    position: int = Field(description="Place in the queue for this service and day")
    created_at: datetime
    mode: Literal["off", "auto", "first_come", "manual"]
    status: Literal["waiting", "offered"] = Field(
        description="offered: the client was told about a free spot"
    )
    open_session_id: UUID | None = Field(
        default=None, description="A spot that is free right now for this client"
    )
    open_starts_at: datetime | None = None


@router.get("/waitlist")
def list_waitlist(
    context: ReadDep,
    day: dt.date | None = None,
    location_id: UUID | None = None,
    service_id: UUID | None = None,
    mode: Literal["auto", "first_come", "manual"] | None = None,
) -> list[WaitlistEntry]:
    """Everyone waiting for a spot, by day: requests and places on classes' own lists."""
    rows = context.session.execute(
        text(ENTRIES_SQL),
        {"day": day, "location": location_id, "service": service_id, "mode": mode},
    ).mappings()
    return [WaitlistEntry.model_validate(dict(row)) for row in rows]


class WaitlistServiceCount(BaseModel):
    service_id: UUID
    name: str
    waiting: int


class WaitlistSummary(BaseModel):
    waiting: int
    services: list[WaitlistServiceCount] = Field(description="The most wanted services")


@router.get("/waitlist/summary")
def waitlist_summary(context: ReadDep) -> WaitlistSummary:
    """How many people wait, and for what (the dashboard's hint to open another class)."""
    rows = context.session.execute(
        text("""
            WITH waiting AS (
                SELECT r.service_id FROM app.waitlist_requests r
                WHERE r.status IN ('active', 'offered') AND r.expires_at > now()
                  AND (r.location_id IS NULL OR app.in_branch(r.location_id))
                UNION ALL
                SELECT s.service_id FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
                WHERE b.status = 'waitlisted' AND s.status = 'scheduled' AND s.starts_at > now()
                  AND (s.location_id IS NULL OR app.in_branch(s.location_id))
            )
            SELECT w.service_id, sv.name, count(*)::int AS waiting
            FROM waiting w JOIN app.services sv ON sv.id = w.service_id
            GROUP BY w.service_id, sv.name ORDER BY waiting DESC, sv.name LIMIT 3
        """)
    ).mappings()
    services = [WaitlistServiceCount.model_validate(dict(row)) for row in rows]
    total = context.session.execute(
        text("""
            SELECT (SELECT count(*) FROM app.waitlist_requests r
                    WHERE r.status IN ('active', 'offered') AND r.expires_at > now()
                      AND (r.location_id IS NULL OR app.in_branch(r.location_id)))
                 + (SELECT count(*) FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
                    WHERE b.status = 'waitlisted' AND s.status = 'scheduled'
                      AND s.starts_at > now()
                      AND (s.location_id IS NULL OR app.in_branch(s.location_id)))
        """)
    ).scalar_one()
    return WaitlistSummary(waiting=total, services=services)


class Admitted(BaseModel):
    session_id: UUID
    booking_id: UUID


class AdmitRequest(BaseModel):
    session_id: UUID | None = Field(
        default=None, description="The free spot to use; default: the first one that matches"
    )


def _request(db: Session, request_id: UUID) -> dict:
    row = (
        db.execute(
            text("""
                SELECT id, client_id, location_id FROM app.waitlist_requests
                WHERE id = :id AND status IN ('active', 'offered')
            """),
            {"id": request_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


@router.post("/waitlist/requests/{request_id}/admit")
def admit_request(request_id: UUID, body: AdmitRequest, context: ManageDep) -> Admitted:
    """The team lets a waiting client in (the manual mode's "let in"): books them into the spot
    that opened and tells them."""
    db = context.session
    request = _request(db, request_id)
    ensure_branch_visible(context, request["location_id"])
    session_id = body.session_id
    if session_id is None:
        row = next(
            (
                r
                for r in db.execute(text(ENTRIES_SQL), _no_filters()).mappings()
                if r["id"] == request_id
            ),
            None,
        )
        session_id = row["open_session_id"] if row else None
    if session_id is None:
        raise _conflict("no_free_spot")
    if not db.execute(
        text("SELECT app.waitlist_matches(:r, :s)"), {"r": request_id, "s": session_id}
    ).scalar():
        raise _conflict("spot_does_not_match")
    target, booking_id = take_spot(
        db, context.tenant_id, session_id, request["client_id"], requires_plan=False
    )
    notify_booking(db, booking_id, "booked_by_studio")
    return Admitted(session_id=target, booking_id=booking_id)


@router.post("/waitlist/bookings/{booking_id}/admit")
def admit_booking(booking_id: UUID, context: ManageDep) -> Admitted:
    """The team moves someone from a class's own list into a spot that is free."""
    db = context.session
    row = db.execute(
        text("""
            SELECT b.session_id, b.client_id, s.location_id FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            WHERE b.id = :id AND b.status = 'waitlisted'
        """),
        {"id": booking_id},
    ).first()
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row.location_id)
    _, promoted = take_spot(
        db, context.tenant_id, row.session_id, row.client_id, requires_plan=False
    )
    notify_booking(db, promoted, "booked_by_studio")
    return Admitted(session_id=row.session_id, booking_id=promoted)


@router.delete("/waitlist/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_request(request_id: UUID, context: ManageDep) -> None:
    """The team takes a request off the list."""
    request = _request(context.session, request_id)
    ensure_branch_visible(context, request["location_id"])
    context.session.execute(
        text(
            "UPDATE app.waitlist_requests SET status = 'cancelled', updated_at = now()"
            " WHERE id = :id"
        ),
        {"id": request_id},
    )


@router.post("/waitlist/requests/{request_id}/notify", status_code=status.HTTP_204_NO_CONTENT)
def notify_request(request_id: UUID, context: ManageDep) -> None:
    """The team tells a waiting client about the spot that is free for them now."""
    db = context.session
    request = _request(db, request_id)
    ensure_branch_visible(context, request["location_id"])
    row = next(
        (
            r
            for r in db.execute(text(ENTRIES_SQL), _no_filters()).mappings()
            if r["id"] == request_id
        ),
        None,
    )
    if row is None or row["open_session_id"] is None:
        raise _conflict("no_free_spot")
    db.execute(
        text("""
            WITH offer AS (
                INSERT INTO app.waitlist_offers (tenant_id, session_id, client_id, request_id)
                VALUES (:tenant, :session, :client, :request)
                ON CONFLICT (session_id, client_id) DO UPDATE
                    SET status = 'open', offered_at = now(), request_id = excluded.request_id
                RETURNING session_id
            ),
            marked AS (
                UPDATE app.waitlist_requests SET status = 'offered', offered_at = now(),
                    offered_session_id = :session, updated_at = now() WHERE id = :request
            )
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT :tenant, :client, 'waitlist_spot_open',
                   jsonb_build_object('session_id', s.id, 'service_name', sv.name,
                                      'starts_at', s.starts_at, 'ends_at', s.ends_at)
            FROM offer o JOIN app.sessions s ON s.id = o.session_id
            JOIN app.services sv ON sv.id = s.service_id
        """),
        {
            "tenant": context.tenant_id,
            "session": row["open_session_id"],
            "client": request["client_id"],
            "request": request_id,
        },
    )


def _no_filters() -> dict:
    return {"day": None, "location": None, "service": None, "mode": None}


# --- The client's side -------------------------------------------------------------------------


class WaitlistRequestCreate(BaseModel):
    service_id: UUID
    kind: Literal["slot", "range", "day"]
    day: dt.date | None = Field(default=None, description="The local day (a slot's own day)")
    from_time: dt.time | None = Field(default=None, description="Range: from (local time)")
    to_time: dt.time | None = Field(default=None, description="Range: to (local time)")
    starts_at: datetime | None = Field(default=None, description="Slot: the exact start")
    staff_user_id: UUID | None = Field(default=None, description="Only with this person")
    location_id: UUID | None = Field(default=None, description="Only at this branch")

    @model_validator(mode="after")
    def fits_its_kind(self) -> "WaitlistRequestCreate":
        if self.kind == "slot":
            if self.starts_at is None:
                raise ValueError("a slot needs starts_at")
            if self.from_time or self.to_time:
                raise ValueError("a slot has no time range")
        elif self.starts_at is not None:
            raise ValueError("only a slot has starts_at")
        if self.kind == "range":
            if self.from_time is None or self.to_time is None or self.to_time <= self.from_time:
                raise ValueError("a range needs from_time before to_time")
        elif self.from_time or self.to_time:
            raise ValueError("only a range has from_time and to_time")
        if self.kind != "slot" and self.day is None:
            raise ValueError("day is required")
        return self


class MyWaitlistEntry(BaseModel):
    id: UUID
    source: Literal["request", "booking"]
    service_id: UUID
    service_name: str
    kind: EntryKind
    session_id: UUID | None = None
    day: dt.date
    from_time: dt.time | None = None
    to_time: dt.time | None = None
    starts_at: datetime | None = None
    staff_name: str | None = None
    position: int | None = None
    created_at: datetime
    offer_session_id: UUID | None = Field(
        default=None, description="A spot is free and the client can take it now"
    )
    offer_starts_at: datetime | None = None


MY_ENTRIES_SQL = """
    WITH entries AS (
        SELECT r.id, 'request' AS source, r.service_id, r.kind, NULL::uuid AS session_id, r.day,
               r.from_time, r.to_time, r.starts_at, r.staff_user_id, NULL::int AS position,
               r.created_at, NULL::uuid AS own_session
        FROM app.waitlist_requests r
        WHERE r.client_id = app.current_client_id() AND r.status IN ('active', 'offered')
          AND r.expires_at > now()
        UNION ALL
        SELECT b.id, 'booking', s.service_id, 'session', s.id,
               (s.starts_at AT TIME ZONE t.time_zone)::date, NULL, NULL, s.starts_at,
               s.instructor_user_id, app.waitlist_position(b.id), b.waitlisted_at, s.id
        FROM app.bookings b
        JOIN app.sessions s ON s.id = b.session_id
        JOIN app.tenants t ON t.id = b.tenant_id
        WHERE b.client_id = app.current_client_id() AND b.status = 'waitlisted'
          AND s.status = 'scheduled' AND s.starts_at > now()
    )
    SELECT e.id, e.source, e.service_id, sv.name AS service_name, e.kind, e.session_id, e.day,
           e.from_time, e.to_time, e.starts_at, st.name AS staff_name, e.position, e.created_at,
           o.session_id AS offer_session_id, os.starts_at AS offer_starts_at
    FROM entries e
    JOIN app.services sv ON sv.id = e.service_id
    LEFT JOIN app.appointment_staff() st ON st.user_id = e.staff_user_id
    LEFT JOIN LATERAL (
        SELECT wo.session_id FROM app.waitlist_offers wo
        WHERE wo.client_id = app.current_client_id() AND wo.status = 'open'
          AND (wo.request_id = e.id OR wo.booking_id = e.id)
          AND app.waitlist_slot_is_free(wo.session_id)
        ORDER BY wo.offered_at DESC LIMIT 1
    ) o ON true
    LEFT JOIN app.sessions os ON os.id = o.session_id
    ORDER BY e.day, e.starts_at NULLS LAST, e.created_at
"""


@client_router.get("/waitlist")
def my_waitlist(context: ClientDep) -> list[MyWaitlistEntry]:
    """What the signed-in client waits for: their requests and their places on classes' lists."""
    rows = context.session.execute(text(MY_ENTRIES_SQL)).mappings()
    return [MyWaitlistEntry.model_validate(dict(row)) for row in rows]


@client_router.post("/waitlist", status_code=status.HTTP_201_CREATED)
def join_waitlist(body: WaitlistRequestCreate, context: ClientDep) -> MyWaitlistEntry:
    """ "Tell me if something opens": a given time, a range of hours or a whole day."""
    db = context.session
    service = (
        db.execute(
            text("SELECT booking_mode, on_site FROM app.services WHERE id = :id AND active"),
            {"id": body.service_id},
        )
        .mappings()
        .first()
    )
    if service is None:
        raise not_found()
    if service["on_site"]:
        raise HTTPException(status_code=422, detail="waitlist_not_available")
    if mode_for(db, body.service_id) == "off":
        raise _conflict("waitlist_off")
    zone, today = db.execute(
        text(
            "SELECT time_zone, (now() AT TIME ZONE time_zone)::date FROM app.tenants WHERE id = :t"
        ),
        {"t": context.tenant_id},
    ).one()
    if body.kind == "slot":
        assert body.starts_at is not None
        day = body.starts_at.astimezone(ZoneInfo(zone)).date()
    else:
        assert body.day is not None
        day = body.day
    expires_at = request_expiry(body.kind, day, body.to_time, body.starts_at, zone)
    if day < today or expires_at <= datetime.now(dt.UTC):
        raise HTTPException(status_code=422, detail="in_the_past")
    ensure_may_book(db, context.tenant_id, context.client_id)
    active = db.execute(
        text("""
            SELECT count(*) FROM app.waitlist_requests
            WHERE client_id = :c AND status IN ('active', 'offered') AND expires_at > now()
        """),
        {"c": context.client_id},
    ).scalar_one()
    if active >= MAX_ACTIVE_REQUESTS:
        raise _conflict("too_many_requests")
    duplicate = db.execute(
        text("""
            SELECT 1 FROM app.waitlist_requests
            WHERE client_id = :c AND status IN ('active', 'offered') AND expires_at > now()
              AND service_id = :service AND kind = :kind AND day = :day
              AND from_time IS NOT DISTINCT FROM :from_time
              AND to_time IS NOT DISTINCT FROM :to_time
              AND starts_at IS NOT DISTINCT FROM :starts_at
              AND staff_user_id IS NOT DISTINCT FROM :staff
              AND location_id IS NOT DISTINCT FROM :location
        """),
        {
            "c": context.client_id,
            "service": body.service_id,
            "kind": body.kind,
            "day": day,
            "from_time": body.from_time,
            "to_time": body.to_time,
            "starts_at": body.starts_at,
            "staff": body.staff_user_id,
            "location": body.location_id,
        },
    ).first()
    if duplicate:
        raise _conflict("already_waiting")
    try:
        request_id = db.execute(
            text("""
                INSERT INTO app.waitlist_requests
                    (tenant_id, client_id, kind, service_id, staff_user_id, location_id, day,
                     from_time, to_time, starts_at, expires_at)
                VALUES (:tenant, :client, :kind, :service, :staff, :location, :day, :from_time,
                        :to_time, :starts_at, :expires_at)
                RETURNING id
            """),
            {
                "tenant": context.tenant_id,
                "client": context.client_id,
                "kind": body.kind,
                "service": body.service_id,
                "staff": body.staff_user_id,
                "location": body.location_id,
                "day": day,
                "from_time": body.from_time,
                "to_time": body.to_time,
                "starts_at": body.starts_at,
                "expires_at": expires_at,
            },
        ).scalar_one()
    except Exception as error:  # a staff member or branch that is not this business's
        if "foreign key" in str(error).lower():
            raise HTTPException(status_code=422, detail="invalid_reference") from error
        raise
    return _my_entry(db, request_id)


def _my_entry(db: Session, entry_id: UUID) -> MyWaitlistEntry:
    for row in db.execute(text(MY_ENTRIES_SQL)).mappings():
        if row["id"] == entry_id:
            return MyWaitlistEntry.model_validate(dict(row))
    raise not_found()


@client_router.delete("/waitlist/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave_waitlist(request_id: UUID, context: ClientDep) -> None:
    """The client stops waiting (a place on a class's own list is cancelled as a booking)."""
    result = context.session.execute(
        text("""
            UPDATE app.waitlist_requests SET status = 'cancelled', updated_at = now()
            WHERE id = :id AND client_id = :c AND status IN ('active', 'offered')
        """),
        {"id": request_id, "c": context.client_id},
    )
    if result.rowcount == 0:
        raise not_found()


class ClaimBody(BaseModel):
    session_id: UUID = Field(description="The spot the client was told about")
    pay: bool = Field(default=False, description="Courts paid in the app: the client agreed to pay")
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=80)


class Claimed(BaseModel):
    session_id: UUID
    booking_id: UUID


@client_router.post("/waitlist/claim", status_code=status.HTTP_201_CREATED)
def claim_spot(body: ClaimBody, context: ClientDep) -> Claimed:
    """ "First to take it gets it": the client takes the spot they were told about. 409
    `spot_taken` when someone was faster (they stay on the list)."""
    db = context.session
    offer = db.execute(
        text("""
            SELECT status FROM app.waitlist_offers
            WHERE session_id = :s AND client_id = :c
        """),
        {"s": body.session_id, "c": context.client_id},
    ).scalar()
    if offer is None:
        raise not_found()
    if offer != "open":
        raise _conflict("spot_taken")
    ensure_may_book(db, context.tenant_id, context.client_id)
    tenant = (
        db.execute(
            text("SELECT booking_requires_plan, resource_payment FROM app.tenants WHERE id = :id"),
            {"id": context.tenant_id},
        )
        .mappings()
        .one()
    )
    mode = db.execute(
        text("""
            SELECT sv.booking_mode FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.id = :id
        """),
        {"id": body.session_id},
    ).scalar_one()
    in_app = mode == "resource" and tenant["resource_payment"] == "app"
    if in_app and not (body.pay and body.idempotency_key):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="payment_required")
    session_id, booking_id = take_spot(
        db,
        context.tenant_id,
        body.session_id,
        context.client_id,
        requires_plan=tenant["booking_requires_plan"] and mode == "class",
    )
    if in_app:
        payment_id = db.execute(
            text("SELECT app.pay_reservation(:booking, :key)"),
            {"booking": booking_id, "key": body.idempotency_key},
        ).scalar_one()
        _payment(db, payment_id)
    return Claimed(session_id=session_id, booking_id=booking_id)
