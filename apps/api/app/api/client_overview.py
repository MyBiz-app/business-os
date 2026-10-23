"""The client app's "all mine" view: one person, every business they are a client of.

Each business keeps its own client record, so this walks the person's businesses one at a time.
Every query runs under that business's own client policies (the same `X-Tenant-Id` scoping as
the rest of /client), so a business is only ever asked about its own client's rows. Nothing here
is visible to a business, and a business never learns that its client uses another one."""

import datetime as dt
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.client_app import BUSINESS_SELECT, ClientBusiness, _business
from app.api.deps import ClientContext, SessionDep, ensure_client_business_open
from app.api.documents import _list as list_documents
from app.api.friends import my_invites
from app.api.health import _business_form, health_state
from app.api.pagination import Page
from app.api.plans import list_entitlements
from app.api.quotes import my_quotes
from app.api.reviews import pending_reviews
from app.core.db import set_tenant

router = APIRouter(prefix="/client", tags=["client"])

MAX_BUSINESSES = 50
PER_BUSINESS = 20
DORMANT_AFTER = dt.timedelta(days=30)
FRIENDS_WINDOW = dt.timedelta(days=7)
PAGE = Page(limit=50, offset=0)

WaitingKind = Literal["health", "document", "payment", "quote", "invite", "review"]


class OverviewBusiness(BaseModel):
    business: ClientBusiness
    waiting: int = Field(description="How many things wait for the client here (the dot)")
    upcoming: int = Field(description="Upcoming bookings here")
    last_visit_at: datetime | None
    dormant: bool = Field(description="Nothing upcoming, no live card, no visit for 30 days")


class OverviewVisit(BaseModel):
    business_id: UUID
    booking_id: UUID
    session_id: UUID
    service_id: UUID
    service_name: str
    booking_mode: str = Field(description="class, appointment or resource")
    starts_at: datetime
    ends_at: datetime
    status: Literal["booked", "waitlisted"]
    location_name: str | None
    room_name: str | None
    instructor_name: str | None
    friends: list[str] = Field(description="First names of friends in the same session")


class OverviewCard(BaseModel):
    business_id: UUID
    entitlement_id: UUID
    name: str
    kind: str
    credits_remaining: int | None
    ends_on: dt.date
    state: str


class OverviewWaiting(BaseModel):
    business_id: UUID
    kind: WaitingKind
    title: str | None = Field(
        description="What it is about (a document, a quote), if it has a name"
    )
    ref: str | None = Field(description="The thing's id, number or token, to open it")


class OverviewRebook(BaseModel):
    business_id: UUID
    service_id: UUID
    service_name: str
    booking_mode: str
    room_id: UUID | None
    room_name: str | None
    instructor_user_id: UUID | None
    instructor_name: str | None
    last_at: datetime


class ClientOverview(BaseModel):
    businesses: list[OverviewBusiness]
    next: list[OverviewVisit] = Field(
        description="Upcoming bookings of every business, soonest first"
    )
    cards: list[OverviewCard] = Field(description="Memberships and passes that are live now")
    waiting: list[OverviewWaiting]
    rebook: list[OverviewRebook] = Field(description="Things the client did before, to book again")


UPCOMING = """
    SELECT b.id AS booking_id, b.status, s.id AS session_id, s.starts_at, s.ends_at,
           sv.id AS service_id, sv.name AS service_name, sv.booking_mode,
           l.name AS location_name, r.name AS room_name, ins.full_name AS instructor_name
    FROM app.bookings b
    JOIN app.sessions s ON s.id = b.session_id
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.locations l ON l.id = s.location_id
    LEFT JOIN app.rooms r ON r.id = s.room_id
    LEFT JOIN LATERAL app.client_instructor(s.instructor_user_id) ins ON true
    WHERE b.client_id = app.current_client_id() AND b.status IN ('booked', 'waitlisted')
      AND s.status = 'scheduled' AND s.ends_at > now()
    ORDER BY s.starts_at
    LIMIT :limit
"""

PAST = """
    SELECT DISTINCT ON (s.service_id, s.room_id, s.instructor_user_id)
           sv.id AS service_id, sv.name AS service_name, sv.booking_mode,
           s.room_id, r.name AS room_name, s.instructor_user_id, ins.full_name AS instructor_name,
           s.starts_at AS last_at
    FROM app.bookings b
    JOIN app.sessions s ON s.id = b.session_id
    JOIN app.services sv ON sv.id = s.service_id AND sv.active
    LEFT JOIN app.rooms r ON r.id = s.room_id
    LEFT JOIN LATERAL app.client_instructor(s.instructor_user_id) ins ON true
    WHERE b.client_id = app.current_client_id() AND b.status IN ('booked', 'checked_in')
      AND s.status = 'scheduled' AND s.ends_at < now()
    ORDER BY s.service_id, s.room_id, s.instructor_user_id, s.starts_at DESC
"""


def _friends_in(db: Session, session_id: UUID) -> list[str]:
    """Friends booked into the same session (the business's participant list rules apply)."""
    try:
        with db.begin_nested():
            return list(
                db.execute(
                    text("""
                        SELECT first_name FROM app.social_participants(:id)
                        WHERE friendship = 'friends' ORDER BY first_name
                    """),
                    {"id": session_id},
                ).scalars()
            )
    except DBAPIError:
        return []


def _waiting(
    db: Session, context: ClientContext
) -> list[tuple[WaitingKind, str | None, str | None]]:
    items: list[tuple[WaitingKind, str | None, str | None]] = []
    _, required, _ = _business_form(db)
    if required and health_state(db, context.client_id) in (
        "missing",
        "expired",
        "expiring",
        "needs_review",
        "rejected",
    ):
        items.append(("health", None, None))
    for document in list_documents(db, context.client_id, PAGE):
        if document.sign_requested and not document.signed_at:
            items.append(("document", document.name, str(document.id)))
    for quote in my_quotes(context, PAGE):
        if quote.deposit_due > 0:
            items.append(("payment", quote.title, quote.token))
        elif quote.status == "sent":
            items.append(("quote", quote.title, quote.token))
    try:
        with db.begin_nested():
            for invite in my_invites(context):
                if invite.direction == "received" and invite.status == "pending":
                    items.append(("invite", invite.service_name, str(invite.id)))
    except HTTPException:  # the business has no friends feature
        pass
    for review in pending_reviews(context):
        items.append(("review", review.service_name, str(review.booking_id)))
    return items


def _one_business(
    db: Session, row: dict, now: datetime
) -> tuple[
    OverviewBusiness,
    list[OverviewVisit],
    list[OverviewCard],
    list[OverviewWaiting],
    list[OverviewRebook],
]:
    business = _business(row)
    tenant_id = business.id
    set_tenant(db, tenant_id)
    ensure_client_business_open(db, tenant_id)
    context = ClientContext(session=db, tenant_id=tenant_id, client_id=business.client_id)

    visits = []
    for item in db.execute(text(UPCOMING), {"limit": PER_BUSINESS}).mappings():
        soon = item["starts_at"] - now < FRIENDS_WINDOW
        visits.append(
            OverviewVisit(
                business_id=tenant_id,
                friends=_friends_in(db, item["session_id"]) if soon else [],
                **item,
            )
        )
    cards = [
        OverviewCard(
            business_id=tenant_id,
            entitlement_id=e.id,
            name=e.name,
            kind=e.kind,
            credits_remaining=e.credits_remaining,
            ends_on=e.ends_on,
            state=e.state,
        )
        for e in list_entitlements(db, business.client_id, PAGE)
        if e.state in ("active", "frozen")
    ]
    waiting = [
        OverviewWaiting(business_id=tenant_id, kind=kind, title=title, ref=ref)
        for kind, title, ref in _waiting(db, context)
    ]
    booked = {(v.service_id, v.room_name) for v in visits}
    past = [dict(item) for item in db.execute(text(PAST)).mappings()]
    past.sort(key=lambda item: item["last_at"], reverse=True)
    rebook = [
        OverviewRebook(business_id=tenant_id, **item)
        for item in past
        if (item["service_id"], item["room_name"]) not in booked
    ][:3]
    last_visit = max((item["last_at"] for item in past), default=None)
    overview = OverviewBusiness(
        business=business,
        waiting=len(waiting),
        upcoming=len(visits),
        last_visit_at=last_visit,
        dormant=not visits
        and not cards
        and (last_visit is None or now - last_visit > DORMANT_AFTER),
    )
    return overview, visits, cards, waiting, rebook


@router.get("/overview")
def my_overview(session: SessionDep) -> ClientOverview:
    """Everything the signed-in person has across the businesses they joined as a client: what
    is next, their live cards, what waits for them and what they could book again. Only the
    person's own rows, read business by business under that business's client policies; a
    business that is closed, suspended or has no client app is left out."""
    now = dt.datetime.now(dt.UTC)
    rows = [
        dict(row)
        for row in session.execute(
            text(f"{BUSINESS_SELECT} ORDER BY t.name LIMIT :limit"), {"limit": MAX_BUSINESSES}
        ).mappings()
    ]
    result = ClientOverview(businesses=[], next=[], cards=[], waiting=[], rebook=[])
    for row in rows:
        try:
            with session.begin_nested():
                overview, visits, cards, waiting, rebook = _one_business(session, row, now)
        except HTTPException:
            continue  # closed, suspended or without the client app: not offered
        result.businesses.append(overview)
        result.next += visits
        result.cards += cards
        result.waiting += waiting
        result.rebook += rebook
    result.next.sort(key=lambda visit: visit.starts_at)
    result.rebook.sort(key=lambda item: item.last_at, reverse=True)
    return result
