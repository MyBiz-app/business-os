"""The client app: end customers join a business, browse its schedule and book themselves.

Clients are not members of the business. Their requests run under the client policies
(see migration 0008): they read the business's catalog and schedule and only their own
client record and bookings."""

import datetime as dt
from collections.abc import Mapping
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
from app.api.schedule import ClosedDay, JobStatus, ServiceSummary
from app.scheduling import local_to_utc
from app.verticals import CATALOG

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
    inquiries: bool = Field(
        default=False, description="Whether its public inquiry form is open (CRM module)"
    )


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
    resource_payment: Literal["app", "venue"] = Field(
        default="app", description="Reservations: paid in the app when booking, or at the venue"
    )
    dependents: Literal["pet", "child"] | None = Field(
        default=None, description="The industry keeps the client's pets / children (#43)"
    )
    dependent_required: bool = Field(
        default=False, description="Every booking says which pet / child comes"
    )
    client_id: UUID
    first_name: str
    last_name: str | None
    phone: str | None


def _business(row: Mapping[str, object]) -> ClientBusiness:
    pack = CATALOG.get(str(row["vertical"]))
    return ClientBusiness.model_validate(
        {
            **row,
            "dependents": pack.dependents if pack else None,
            "dependent_required": pack.dependent_required if pack else False,
        }
    )


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
    dependent_id: UUID | None = None
    dependent_name: str | None = Field(default=None, description="The pet / child who comes")


class ClientBookingCreate(BaseModel):
    dependent_id: UUID | None = Field(
        default=None, description="Which of the client's pets / children comes (#43)"
    )


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
    address: str | None = Field(default=None, description="My on-site job: where (#42)")
    job_status: JobStatus | None = Field(default=None, description="My on-site job's progress")
    my_booking: MyBooking | None = Field(description="The client's first live booking")
    my_bookings: list[MyBooking] = Field(
        default_factory=list,
        description="All the client's live bookings (one per dependent who comes)",
    )


@public_router.get("/public/businesses/{code}")
def business_by_code(code: str, session: AnonymousSessionDep) -> BusinessProfile:
    row = (
        session.execute(
            text(f"""
                SELECT t.id, t.name, t.locale, t.primary_color, t.client_app,
                       {LOGO_URL.format(t="t")} AS logo_url,
                       app.accepts_inquiries(:code) AS inquiries
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
           t.cancellation_window_minutes, t.online_sales, t.resource_payment,
           {LOGO_URL.format(t="t")} AS logo_url,
           c.id AS client_id, c.first_name, c.last_name, c.phone
    FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
    WHERE c.user_id = app.current_user_id()
"""


@router.get("/businesses")
def my_businesses(session: SessionDep) -> list[ClientBusiness]:
    """Every business the signed-in user has joined as a client."""
    rows = session.execute(text(f"{BUSINESS_SELECT} ORDER BY t.name")).mappings()
    return [_business(row) for row in rows]


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
    return _business(row)


CLIENT_SESSION_SELECT = """
    SELECT s.id, s.starts_at, s.ends_at, s.status, s.capacity,
           l.name AS location_name, r.name AS room_name,
           greatest(s.capacity - bk.booked, 0) AS spots_left, bk.waitlisted,
           sv.id AS service_id, sv.name AS service_name, sv.color AS service_color,
           mine.items AS my_bookings,
           CASE WHEN mine.items IS NOT NULL THEN s.address END AS address,
           CASE WHEN mine.items IS NOT NULL THEN s.job_status END AS job_status
    FROM app.sessions s
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.locations l ON l.id = s.location_id
    LEFT JOIN app.rooms r ON r.id = s.room_id
    CROSS JOIN LATERAL app.session_counts(s.id) bk
    CROSS JOIN LATERAL (
        SELECT json_agg(json_build_object(
                   'id', b.id, 'status', b.status,
                   'waitlist_position', app.waitlist_position(b.id),
                   'dependent_id', b.dependent_id, 'dependent_name', d.name
               ) ORDER BY b.created_at) AS items
        FROM app.bookings b
        LEFT JOIN app.dependents d ON d.id = b.dependent_id
        WHERE b.session_id = s.id AND b.client_id = app.current_client_id()
          AND b.status <> 'cancelled'
    ) mine
"""


def _to_session(row: dict) -> ClientSession:
    data = dict(row)
    data["service"] = {
        "id": data.pop("service_id"),
        "name": data.pop("service_name"),
        "color": data.pop("service_color"),
    }
    data["my_bookings"] = data["my_bookings"] or []
    data["my_booking"] = data["my_bookings"][0] if data["my_bookings"] else None
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
    return _business(row)


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
              AND (sv.booking_mode = 'class' OR mine.items IS NOT NULL)
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
def book_session(
    session_id: UUID, context: ClientDep, body: ClientBookingCreate | None = None
) -> ClientSession:
    """Books the signed-in client (or one of their pets / children), or puts them on the
    waitlist when the session is full."""
    _ensure_upcoming(context, session_id)
    mode = context.session.execute(
        text("""
            SELECT sv.booking_mode FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.id = :id
        """),
        {"id": session_id},
    ).scalar()
    if mode != "class":  # appointments and reservations are booked at a free time
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
        dependent_id=body.dependent_id if body else None,
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
                   s.status AS session_status, b.status, b.late_cancel,
                   d.name AS dependent_name,
                   (SELECT r.rating FROM app.reviews r WHERE r.booking_id = b.id) AS rating
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            LEFT JOIN app.dependents d ON d.id = b.dependent_id
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
