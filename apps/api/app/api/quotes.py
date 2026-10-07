"""Quotes, deposits and event projects (#44, decision X12).

Staff write a quote for a client (lines, a deposit percentage, an optional event), send it, and
the client answers it by its private link (no sign-in) or in the client app. An accepted quote's
deposit is paid from the link (simulated until a payment provider is chosen); staff record the
rest. An accepted quote with an event date is the event's project (listed under events).

Only a draft is edited; a sent quote is changed by copying it into a new draft."""

import datetime as dt
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, ensure_not_erased, not_found
from app.api.deps import AnonymousSessionDep, ClientDep, TenantContext, require
from app.core.config import get_settings
from app.permissions import Permission
from app.providers.choice import choose
from app.providers.payments import CheckoutRequest, PaymentsUnavailable
from app.scheduling import local_to_utc

router = APIRouter(tags=["quotes"])
public_router = APIRouter(prefix="/public/quotes", tags=["quotes"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]

QuoteStatus = Literal["draft", "sent", "accepted", "declined", "expired"]
PaymentMethod = Literal["cash", "card", "transfer", "other"]


class QuoteLine(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Field(gt=0, le=100000, decimal_places=2)
    unit_price: int = Field(ge=0, description="Minor units")

    @field_validator("description", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class QuoteFields(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    lines: list[QuoteLine] = Field(min_length=1, max_length=50)
    deposit_percent: int = Field(default=0, ge=0, le=100)
    valid_until: dt.date | None = None
    event_date: dt.date | None = Field(default=None, description="The event's local date, if any")
    event_time: dt.time | None = Field(default=None, description="The event's local start time")
    event_place: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000, description="Terms, what's included")

    @field_validator("title", "event_place", "notes", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class QuoteCreate(QuoteFields):
    client_id: UUID


class QuoteSummary(BaseModel):
    id: UUID
    number: int
    kind: Literal["quote", "bill"] = Field(
        default="quote", description="bill: a month of time and retainer (#45)"
    )
    title: str
    client_id: UUID
    client_name: str
    status: QuoteStatus = Field(description="expired: sent and past its date")
    currency: str
    total: int
    paid: int
    deposit_due: int = Field(description="What's left of the deposit (accepted quotes)")
    event_starts_at: datetime | None
    event_place: str | None
    valid_until: dt.date | None
    created_at: datetime


class Quote(QuoteSummary):
    lines: list[QuoteLine]
    deposit_percent: int
    notes: str | None
    token: str = Field(description="The private link: /q/{token}")
    sent_at: datetime | None
    accepted_at: datetime | None
    accepted_name: str | None
    declined_at: datetime | None


class PublicQuote(BaseModel):
    """What the client sees by the private link."""

    number: int
    kind: Literal["quote", "bill"] = "quote"
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    title: str
    status: QuoteStatus
    currency: str
    lines: list[QuoteLine]
    total: int
    paid: int
    deposit_percent: int
    deposit_due: int
    valid_until: dt.date | None
    event_starts_at: datetime | None
    event_place: str | None
    notes: str | None
    accepted_at: datetime | None
    accepted_name: str | None
    business_name: str
    business_locale: Literal["he", "en"]
    business_color: str | None
    time_zone: str
    client_name: str


class Answer(BaseModel):
    accept: bool
    name: str | None = Field(default=None, max_length=120, description="Who accepts")


class DepositPayment(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)


class DepositResult(PublicQuote):
    pay_url: str | None = Field(
        default=None, description="A real payments provider: pay the deposit on its page"
    )


class StaffPayment(BaseModel):
    amount: int = Field(gt=0, description="Minor units")
    method: PaymentMethod = "cash"
    idempotency_key: str = Field(min_length=8, max_length=100)


EXPIRED = """
    CASE WHEN q.status = 'sent' AND q.valid_until
              < (now() AT TIME ZONE t.time_zone)::date THEN 'expired' ELSE q.status END
"""
SUMMARY = f"""
    SELECT q.id, q.number, q.kind, q.title, q.client_id,
           trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           {EXPIRED} AS status, q.currency,
           app.quote_total(q.id) AS total, app.quote_paid(q.id) AS paid,
           CASE WHEN q.status = 'accepted' THEN greatest(
               round(app.quote_total(q.id) * q.deposit_percent / 100.0)::integer
               - app.quote_paid(q.id), 0) ELSE 0 END AS deposit_due,
           q.event_starts_at, q.event_place, q.valid_until, q.created_at
"""
FROM = """
    FROM app.quotes q
    JOIN app.clients c ON c.id = q.client_id
    JOIN app.tenants t ON t.id = q.tenant_id
"""
DETAIL = f"""
    {SUMMARY}, q.deposit_percent, q.notes, q.token, q.sent_at, q.accepted_at,
           q.accepted_name, q.declined_at,
           coalesce((
               SELECT jsonb_agg(jsonb_build_object(
                   'description', l.description, 'quantity', l.quantity,
                   'unit_price', l.unit_price) ORDER BY l.position)
               FROM app.quote_lines l WHERE l.quote_id = q.id
           ), '[]'::jsonb) AS lines
    {FROM}
"""


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _load(db: Session, quote_id: UUID) -> Quote:
    row = db.execute(text(f"{DETAIL} WHERE q.id = :id"), {"id": quote_id}).mappings().first()
    if row is None:
        raise not_found()
    return Quote.model_validate(dict(row))


def _write_lines(db: Session, tenant_id: UUID, quote_id: UUID, lines: list[QuoteLine]) -> None:
    db.execute(text("DELETE FROM app.quote_lines WHERE quote_id = :id"), {"id": quote_id})
    db.execute(
        text("""
            INSERT INTO app.quote_lines
                (tenant_id, quote_id, position, description, quantity, unit_price)
            VALUES (:tenant_id, :quote_id, :position, :description, :quantity, :unit_price)
        """),
        [
            {
                "tenant_id": tenant_id,
                "quote_id": quote_id,
                "position": i,
                **line.model_dump(),
            }
            for i, line in enumerate(lines)
        ],
    )


def _fields(db: Session, body: QuoteFields) -> dict:
    """The quote's columns; the event's local date and time become an instant in the
    business's time zone."""
    if body.title is None:
        raise HTTPException(status_code=422, detail="title must not be blank")
    fields = body.model_dump(exclude={"lines", "event_date", "event_time"})
    fields["event_starts_at"] = None
    if body.event_date is not None:
        time_zone = db.execute(
            text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar_one()
        fields["event_starts_at"] = local_to_utc(
            body.event_date, body.event_time or time(0, 0), time_zone
        )
    return fields


# --- Staff ------------------------------------------------------------------------------------


@router.get("/quotes")
def list_quotes(
    context: ReadDep,
    client_id: Annotated[UUID | None, Query()] = None,
    quote_status: Annotated[QuoteStatus | None, Query(alias="status")] = None,
) -> list[QuoteSummary]:
    """Quotes, newest first; by client or status (expired = sent and past its date)."""
    rows = context.session.execute(
        text(f"""
            SELECT * FROM ({SUMMARY} {FROM}) q
            WHERE (CAST(:client AS uuid) IS NULL OR q.client_id = :client)
              AND (CAST(:status AS text) IS NULL OR q.status = :status)
            ORDER BY q.number DESC
            LIMIT 300
        """),
        {"client": client_id, "status": quote_status},
    ).mappings()
    return [QuoteSummary.model_validate(dict(row)) for row in rows]


@router.post("/quotes", status_code=status.HTTP_201_CREATED)
def create_quote(body: QuoteCreate, context: SalesDep) -> Quote:
    db = context.session
    ensure_not_erased(db, body.client_id)
    try:
        quote_id = db.execute(
            text("""
                INSERT INTO app.quotes
                    (tenant_id, client_id, number, title, currency, deposit_percent,
                     valid_until, event_starts_at, event_place, notes, created_by)
                SELECT :tenant_id, :client_id, app.next_quote_number(), :title, t.currency,
                       :deposit_percent, :valid_until, :event_starts_at, :event_place, :notes,
                       app.current_user_id()
                FROM app.tenants t WHERE t.id = :tenant_id
                RETURNING id
            """),
            {**_fields(db, body), "client_id": body.client_id, "tenant_id": context.tenant_id},
        ).scalar_one()
    except IntegrityError as error:  # no such client in this business
        raise HTTPException(status_code=422, detail="invalid_reference") from error
    _write_lines(db, context.tenant_id, quote_id, body.lines)
    return _load(db, quote_id)


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: UUID, context: ReadDep) -> Quote:
    return _load(context.session, quote_id)


@router.put("/quotes/{quote_id}")
def update_quote(quote_id: UUID, body: QuoteFields, context: SalesDep) -> Quote:
    """Rewrites a draft (a sent quote is changed by copying it)."""
    db = context.session
    updated = db.execute(
        text("""
            UPDATE app.quotes SET title = :title, deposit_percent = :deposit_percent,
                valid_until = :valid_until, event_starts_at = :event_starts_at,
                event_place = :event_place, notes = :notes, updated_at = now()
            WHERE id = :id AND status = 'draft'
            RETURNING id
        """),
        {**_fields(db, body), "id": quote_id},
    ).first()
    if updated is None:
        _load(db, quote_id)  # 404 when missing
        raise _conflict("not_a_draft")
    _write_lines(db, context.tenant_id, quote_id, body.lines)
    return _load(db, quote_id)


@router.post("/quotes/{quote_id}/send")
def send_quote(quote_id: UUID, context: SalesDep) -> Quote:
    """Marks a draft as sent: its private link now works. Sending again is harmless."""
    db = context.session
    current = _load(db, quote_id)
    if current.status not in ("draft", "sent"):
        raise _conflict("already_answered")
    db.execute(
        text("""
            UPDATE app.quotes SET status = 'sent', sent_at = coalesce(sent_at, now()),
                updated_at = now()
            WHERE id = :id
        """),
        {"id": quote_id},
    )
    return _load(db, quote_id)


@router.post("/quotes/{quote_id}/copy", status_code=status.HTTP_201_CREATED)
def copy_quote(quote_id: UUID, context: SalesDep) -> Quote:
    """A new draft with the same client, lines and terms (a new version of a sent quote)."""
    db = context.session
    current = _load(db, quote_id)
    local = None
    if current.event_starts_at is not None:
        time_zone = db.execute(
            text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar_one()
        local = current.event_starts_at.astimezone(ZoneInfo(time_zone))
    return create_quote(
        QuoteCreate(
            client_id=current.client_id,
            title=current.title,
            lines=current.lines,
            deposit_percent=current.deposit_percent,
            valid_until=None,
            event_date=local.date() if local else None,
            event_time=local.time().replace(tzinfo=None) if local else None,
            event_place=current.event_place,
            notes=current.notes,
        ),
        context,
    )


@router.post("/quotes/{quote_id}/payments", status_code=status.HTTP_201_CREATED)
def record_quote_payment(quote_id: UUID, body: StaffPayment, context: SalesDep) -> Quote:
    """Staff record a payment for an accepted quote (the deposit or the balance, at the venue
    or by transfer); never more than what is left."""
    db = context.session
    current = _load(db, quote_id)
    if current.status != "accepted":
        raise _conflict("not_accepted")
    if body.amount > current.total - current.paid:
        raise HTTPException(status_code=422, detail="more_than_due")
    db.execute(
        text("""
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, method,
                 idempotency_key, created_by, quote_id, description)
            VALUES (:tenant_id, :client_id, :amount, :currency, 'succeeded', 'manual',
                    :method, :key, app.current_user_id(), :quote_id, :description)
            ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        """),
        {
            "tenant_id": context.tenant_id,
            "client_id": current.client_id,
            "amount": body.amount,
            "currency": current.currency,
            "method": body.method,
            "key": body.idempotency_key,
            "quote_id": quote_id,
            "description": f"{current.title[:180]} · {current.number}",
        },
    )
    return _load(db, quote_id)


@router.get("/events")
def events(
    context: ReadDep,
    start: Annotated[dt.date, Query(description="First local date")],
    days: Annotated[int, Query(ge=1, le=366)] = 90,
) -> list[QuoteSummary]:
    """Event projects: accepted quotes with an event date in the window, soonest first."""
    db = context.session
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    begin = local_to_utc(start, time.min, time_zone)
    rows = db.execute(
        text(f"""
            {SUMMARY} {FROM}
            WHERE q.status = 'accepted' AND q.event_starts_at >= :from
              AND q.event_starts_at < :to
            ORDER BY q.event_starts_at
        """),
        {"from": begin, "to": begin + timedelta(days=days)},
    ).mappings()
    return [QuoteSummary.model_validate(dict(row)) for row in rows]


# --- The private link (no sign-in) ------------------------------------------------------------


def _public(db: Session, token: str) -> PublicQuote:
    data = db.execute(text("SELECT app.quote_by_token(:token)"), {"token": token}).scalar()
    if data is None:
        raise not_found()
    today = datetime.now(ZoneInfo(data["time_zone"])).date()
    expired = (
        data["status"] == "sent"
        and data["valid_until"] is not None
        and dt.date.fromisoformat(data["valid_until"]) < today
    )
    deposit = round(data["total"] * data["deposit_percent"] / 100)
    return PublicQuote.model_validate(
        {
            **data,
            "status": "expired" if expired else data["status"],
            "deposit_due": max(deposit - data["paid"], 0) if data["status"] == "accepted" else 0,
        }
    )


@public_router.get("/{token}")
def public_quote(token: str, session: AnonymousSessionDep) -> PublicQuote:
    return _public(session, token)


@public_router.post("/{token}/answer")
def answer_quote(token: str, body: Answer, session: AnonymousSessionDep) -> PublicQuote:
    """Accepts (with a name) or declines a sent quote that is still valid."""
    try:
        with session.begin_nested():
            session.execute(
                text("SELECT app.answer_quote(:token, :accept, :name)"),
                {"token": token, "accept": body.accept, "name": body.name},
            )
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise not_found() from error
        detail = {"55000": "already_answered", "22008": "expired", "22004": "name_required"}
        if code not in detail:
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT if code != "22004" else 422,
            detail=detail[code],
        ) from error
    return _public(session, token)


@public_router.post("/{token}/deposit", status_code=status.HTTP_201_CREATED)
def pay_deposit(token: str, body: DepositPayment, session: AnonymousSessionDep) -> DepositResult:
    """Pays the deposit of an accepted quote through the business's payments provider (X13):
    the simulated one records it now; a real one returns its payment page, and its webhook
    records the payment."""
    tenant_id = session.execute(text("SELECT app.quote_tenant(:token)"), {"token": token}).scalar()
    if tenant_id is None:
        raise not_found()
    chosen = choose(session, tenant_id, "payments")
    pay_url = None
    try:
        with session.begin_nested():
            if chosen.instance.simulated:
                session.execute(
                    text("SELECT app.pay_quote_deposit(:token, :key)"),
                    {"token": token, "key": body.idempotency_key},
                )
            else:
                checkout_id = session.execute(
                    text("SELECT app.start_quote_checkout(:token, :provider)"),
                    {"token": token, "provider": chosen.info.name},
                ).scalar_one()
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise _conflict("not_accepted") from error
        if code == "55000":
            raise _conflict("nothing_due") from error
        raise
    quote = _public(session, token)
    if not chosen.instance.simulated:
        settings = get_settings()
        link = f"{settings.web_url}/q/{token}"
        try:
            hosted = chosen.instance.create_checkout(
                CheckoutRequest(
                    checkout_id=str(checkout_id),
                    amount=quote.deposit_due,
                    currency=quote.currency,
                    description=f"{quote.title} · {quote.number}",
                    client_name=quote.client_name,
                    client_email=None,
                    success_url=f"{link}?paid=1",
                    cancel_url=link,
                    locale=quote.business_locale,
                )
            )
        except PaymentsUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="payments_unavailable"
            ) from error
        session.execute(
            text("SELECT app.set_checkout_page(:id, :url, :ref)"),
            {"id": checkout_id, "url": hosted.pay_url, "ref": hosted.provider_ref},
        )
        pay_url = hosted.pay_url
    return DepositResult(**quote.model_dump(), pay_url=pay_url)


# --- Client app -------------------------------------------------------------------------------


class ClientQuote(BaseModel):
    number: int
    kind: Literal["quote", "bill"] = "quote"
    title: str
    status: QuoteStatus
    total: int
    currency: str
    event_starts_at: datetime | None
    token: str = Field(description="Opens the quote by its private link")


@client_router.get("/quotes")
def my_quotes(context: ClientDep) -> list[ClientQuote]:
    """The client's quotes in this business (sent ones), newest first."""
    rows = context.session.execute(
        text(f"""
            SELECT q.number, q.kind, q.title, {EXPIRED} AS status,
                   app.quote_total(q.id) AS total,
                   q.currency, q.event_starts_at, q.token
            FROM app.quotes q JOIN app.tenants t ON t.id = q.tenant_id
            WHERE q.client_id = app.current_client_id() AND q.status <> 'draft'
            ORDER BY q.number DESC
        """)
    ).mappings()
    return [ClientQuote.model_validate(dict(row)) for row in rows]
