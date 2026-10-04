"""The client app: end customers join a business, browse its schedule and book themselves.

Clients are not members of the business. Their requests run under the client policies
(see migration 0008): they read the business's catalog and schedule and only their own
client record and bookings."""

import datetime as dt
from datetime import datetime, time, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.bookings import (
    BookingStatus,
    ClientBooking,
    cancel_booking,
    lock_session,
    place_booking,
)
from app.api.common import blank_to_none, not_found
from app.api.deps import AnonymousSessionDep, ClientContext, ClientDep, SessionDep, UserDep
from app.api.health import ensure_may_book
from app.api.plans import PLAN_COLUMNS, Entitlement, Plan, list_entitlements
from app.api.routes import ensure_profile
from app.api.schedule import ClosedDay, ServiceSummary
from app.scheduling import local_to_utc

public_router = APIRouter(tags=["client"])
router = APIRouter(prefix="/client", tags=["client"])

LOGO_URL = """
    CASE WHEN {t}.logo_updated_at IS NULL THEN NULL
         ELSE '/public/tenants/' || {t}.id || '/logo?v='
              || extract(epoch FROM {t}.logo_updated_at)::bigint END
"""


class BusinessProfile(BaseModel):
    """What anyone holding a join code may see before signing in."""

    id: UUID
    name: str
    locale: Literal["he", "en"]
    primary_color: str | None
    logo_url: str | None
    client_app: bool = Field(description="Whether the business offers the client app")


class ClientBusiness(BaseModel):
    id: UUID
    name: str
    vertical: str = Field(description="The business's industry (terms in the app follow it)")
    locale: Literal["he", "en"]
    primary_color: str | None
    logo_url: str | None
    time_zone: str
    currency: str
    cancellation_window_minutes: int
    online_sales: bool = Field(description="The client can buy plans in the app")
    client_id: UUID
    first_name: str
    last_name: str | None
    phone: str | None


class ProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("first_name", "last_name", "phone", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return blank_to_none(value)


class JoinRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class MyBooking(BaseModel):
    id: UUID
    status: BookingStatus
    waitlist_position: int | None


class ClientSession(BaseModel):
    id: UUID
    service: ServiceSummary
    location_name: str | None
    room_name: str | None
    starts_at: datetime
    ends_at: datetime
    status: Literal["scheduled", "cancelled"]
    capacity: int
    spots_left: int
    waitlisted: int
    my_booking: MyBooking | None


@public_router.get("/public/businesses/{code}")
def business_by_code(code: str, session: AnonymousSessionDep) -> BusinessProfile:
    row = (
        session.execute(
            text(f"""
                SELECT t.id, t.name, t.locale, t.primary_color, t.client_app,
                       {LOGO_URL.format(t="t")} AS logo_url
                FROM app.business_by_join_code(:code) t
            """),
            {"code": code},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return BusinessProfile.model_validate(dict(row))


BUSINESS_SELECT = f"""
    SELECT t.id, t.name, t.vertical, t.locale, t.primary_color, t.time_zone, t.currency,
           t.cancellation_window_minutes, t.online_sales, {LOGO_URL.format(t="t")} AS logo_url,
           c.id AS client_id, c.first_name, c.last_name, c.phone
    FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
    WHERE c.user_id = app.current_user_id()
"""


@router.get("/businesses")
def my_businesses(session: SessionDep) -> list[ClientBusiness]:
    """Every business the signed-in user has joined as a client."""
    rows = session.execute(text(f"{BUSINESS_SELECT} ORDER BY t.name")).mappings()
    return [ClientBusiness.model_validate(dict(row)) for row in rows]


@router.post("/businesses", status_code=status.HTTP_201_CREATED)
def join_business(body: JoinRequest, user: UserDep, session: SessionDep) -> ClientBusiness:
    ensure_profile(session, user.id, user.email)
    offers_app = session.execute(
        text("SELECT client_app FROM app.business_by_join_code(:code)"), {"code": body.code}
    ).scalar()
    if offers_app is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    client_id = session.execute(
        text("SELECT app.join_business(:code)"), {"code": body.code}
    ).scalar()
    if client_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_code")
    row = (
        session.execute(text(f"{BUSINESS_SELECT} AND c.id = :id"), {"id": client_id})
        .mappings()
        .one()
    )
    return ClientBusiness.model_validate(dict(row))


CLIENT_SESSION_SELECT = """
    SELECT s.id, s.starts_at, s.ends_at, s.status, s.capacity,
           l.name AS location_name, r.name AS room_name,
           greatest(s.capacity - bk.booked, 0) AS spots_left, bk.waitlisted,
           sv.id AS service_id, sv.name AS service_name, sv.color AS service_color,
           mine.id AS my_booking_id, mine.status AS my_booking_status,
           app.waitlist_position(mine.id) AS my_waitlist_position
    FROM app.sessions s
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.locations l ON l.id = s.location_id
    LEFT JOIN app.rooms r ON r.id = s.room_id
    CROSS JOIN LATERAL app.session_counts(s.id) bk
    LEFT JOIN app.bookings mine
        ON mine.session_id = s.id AND mine.client_id = app.current_client_id()
        AND mine.status <> 'cancelled'
"""


def _to_session(row: dict) -> ClientSession:
    data = dict(row)
    data["service"] = {
        "id": data.pop("service_id"),
        "name": data.pop("service_name"),
        "color": data.pop("service_color"),
    }
    booking_id = data.pop("my_booking_id")
    booking_status = data.pop("my_booking_status")
    position = data.pop("my_waitlist_position")
    data["my_booking"] = (
        {"id": booking_id, "status": booking_status, "waitlist_position": position}
        if booking_id
        else None
    )
    return ClientSession.model_validate(data)


def _load_session(db: Session, session_id: UUID) -> ClientSession:
    row = (
        db.execute(text(f"{CLIENT_SESSION_SELECT} WHERE s.id = :id"), {"id": session_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return _to_session(row)


def _time_zone(db: Session) -> str:
    return db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.client_tenant_id()")
    ).scalar_one()


@router.patch("/profile")
def update_profile(body: ProfileUpdate, context: ClientDep) -> ClientBusiness:
    """The client's own name and phone in this business (nothing else)."""
    db = context.session
    db.execute(
        text("SELECT app.update_my_profile(:first_name, :last_name, :phone)"),
        body.model_dump(),
    )
    row = (
        db.execute(text(f"{BUSINESS_SELECT} AND c.id = :id"), {"id": context.client_id})
        .mappings()
        .one()
    )
    return ClientBusiness.model_validate(dict(row))


@router.get("/sessions")
def client_sessions(
    context: ClientDep,
    start: Annotated[dt.date, Query(description="First local date (business time zone)")],
    days: Annotated[int, Query(ge=1, le=14)] = 7,
) -> list[ClientSession]:
    """Upcoming sessions in the window (past ones are left out)."""
    db = context.session
    time_zone = _time_zone(db)
    window_start = max(local_to_utc(start, time.min, time_zone), datetime.now(dt.UTC))
    window_end = local_to_utc(start + timedelta(days=days), time.min, time_zone)
    rows = db.execute(
        text(f"""
            {CLIENT_SESSION_SELECT}
            WHERE s.starts_at >= :from AND s.starts_at < :to
              AND (sv.booking_mode = 'class' OR mine.id IS NOT NULL)
            ORDER BY s.starts_at
        """),
        {"from": window_start, "to": window_end},
    ).mappings()
    return [_to_session(row) for row in rows]


@router.get("/closed-days")
def client_closed_days(
    context: ClientDep,
    start: Annotated[dt.date, Query(description="First local date (business time zone)")],
    days: Annotated[int, Query(ge=1, le=14)] = 7,
) -> list[ClosedDay]:
    """Days the business is closed in the window (no classes; usually a holiday)."""
    rows = context.session.execute(
        text("""
            SELECT id, day, reason FROM app.closed_days
            WHERE day >= :start AND day < :end ORDER BY day
        """),
        {"start": start, "end": start + timedelta(days=days)},
    ).mappings()
    return [ClosedDay.model_validate(dict(row)) for row in rows]


def _ensure_upcoming(context: ClientContext, session_id: UUID) -> None:
    session = lock_session(context.session, session_id)
    if session["starts_at"] <= datetime.now(dt.UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_started")


@router.post("/sessions/{session_id}/bookings", status_code=status.HTTP_201_CREATED)
def book_session(session_id: UUID, context: ClientDep) -> ClientSession:
    """Books the signed-in client, or puts them on the waitlist when the session is full."""
    _ensure_upcoming(context, session_id)
    mode = context.session.execute(
        text("""
            SELECT sv.booking_mode FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.id = :id
        """),
        {"id": session_id},
    ).scalar()
    if mode == "appointment":  # appointments are booked at a free time (POST /appointments)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_bookable")
    ensure_may_book(context.session, context.tenant_id, context.client_id)
    requires_plan = context.session.execute(
        text("SELECT booking_requires_plan FROM app.tenants WHERE id = :id"),
        {"id": context.tenant_id},
    ).scalar_one()
    place_booking(
        context.session,
        context.tenant_id,
        session_id,
        context.client_id,
        requires_plan=requires_plan,
    )
    return _load_session(context.session, session_id)


@router.post("/bookings/{booking_id}/cancel")
def cancel_my_booking(booking_id: UUID, context: ClientDep) -> ClientSession:
    db = context.session
    session_id = db.execute(
        text("SELECT session_id FROM app.bookings WHERE id = :id AND status <> 'cancelled'"),
        {"id": booking_id},
    ).scalar()
    if session_id is None:
        raise not_found()
    _ensure_upcoming(context, session_id)
    cancel_booking(db, booking_id, session_id)
    return _load_session(db, session_id)


@router.get("/bookings")
def my_bookings(context: ClientDep) -> list[ClientBooking]:
    """The client's bookings in this business, newest session first."""
    rows = context.session.execute(
        text("""
            SELECT b.id, b.session_id, sv.name AS service_name, s.starts_at, s.ends_at,
                   s.status AS session_status, b.status, b.late_cancel
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = app.current_client_id()
            ORDER BY s.starts_at DESC
            LIMIT 200
        """)
    ).mappings()
    return [ClientBooking.model_validate(dict(row)) for row in rows]


@router.get("/plans")
def business_plans(context: ClientDep) -> list[Plan]:
    """What the business sells (active plans), to show clients their options."""
    rows = context.session.execute(
        text(f"SELECT {PLAN_COLUMNS} FROM app.plans WHERE active ORDER BY kind, price_amount")
    ).mappings()
    return [Plan.model_validate(dict(row)) for row in rows]


@router.get("/entitlements")
def my_entitlements(context: ClientDep) -> list[Entitlement]:
    return list_entitlements(context.session, context.client_id)
