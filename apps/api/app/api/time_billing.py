"""Time entries, retainers and billing a month (#45, decision X14).

Staff log the time they work for each client; a client can have a retainer (a monthly fee, the
minutes it includes, the hourly rate beyond them). "Bill the month" turns the retainer and the
month's unbilled billable time into a bill: a quote of kind `bill`, already accepted, with the
whole amount due, which the client pays by its private link like a quote's deposit. Billed time
points to its bill and is never billed again."""

import calendar
import datetime as dt
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.common import ensure_not_erased, not_found
from app.api.deps import TenantContext, require
from app.api.quotes import Quote, _load
from app.email import load_all_messages
from app.permissions import Permission

router = APIRouter(tags=["time"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]


class TimeEntry(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str
    user_id: UUID
    user_name: str
    day: dt.date
    minutes: int
    description: str
    billable: bool
    bill_id: UUID | None = Field(description="The bill that billed it; billed time is locked")
    bill_number: int | None
    created_at: datetime


class TimeEntryCreate(BaseModel):
    client_id: UUID
    day: dt.date
    minutes: int = Field(ge=1, le=1440)
    description: str = Field(min_length=1, max_length=500)
    billable: bool = True

    @field_validator("description", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TimeEntryUpdate(BaseModel):
    day: dt.date | None = None
    minutes: int | None = Field(default=None, ge=1, le=1440)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    billable: bool | None = None


class Retainer(BaseModel):
    client_id: UUID
    monthly_amount: int = Field(description="Minor units; 0: hourly only")
    included_minutes: int
    hourly_rate: int = Field(description="Minor units per hour beyond the included minutes")
    currency: str
    active: bool


class RetainerUpdate(BaseModel):
    monthly_amount: int = Field(ge=0)
    included_minutes: int = Field(ge=0, le=100_000)
    hourly_rate: int = Field(ge=0)
    active: bool = True


class BillRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")


ENTRY_SELECT = """
    SELECT e.id, e.client_id, trim(c.first_name || ' ' || coalesce(c.last_name, ''))
               AS client_name,
           e.user_id, coalesce(nullif(u.full_name, ''), u.email) AS user_name,
           e.day, e.minutes, e.description, e.billable, e.bill_id, q.number AS bill_number,
           e.created_at
    FROM app.time_entries e
    JOIN app.clients c ON c.id = e.client_id
    JOIN app.users u ON u.id = e.user_id
    LEFT JOIN app.quotes q ON q.id = e.bill_id
"""


def _entry(db, entry_id: UUID) -> TimeEntry:
    row = db.execute(text(f"{ENTRY_SELECT} WHERE e.id = :id"), {"id": entry_id}).mappings().first()
    if row is None:
        raise not_found()
    return TimeEntry.model_validate(dict(row))


def _editable(context: TenantContext, entry_id: UUID) -> None:
    """Time is changed by who logged it (or a manager), until it is billed."""
    row = (
        context.session.execute(
            text("""
                SELECT user_id = app.current_user_id() AS mine, bill_id
                FROM app.time_entries WHERE id = :id FOR UPDATE
            """),
            {"id": entry_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    if not row["mine"] and Permission.SALES_MANAGE not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if row["bill_id"] is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_billed")


@router.get("/time")
def time_entries(
    context: ReadDep,
    client_id: Annotated[UUID | None, Query()] = None,
    mine: Annotated[bool, Query(description="Only the signed-in user's time")] = False,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to", description="Inclusive")] = None,
) -> list[TimeEntry]:
    """Time entries, newest day first (up to 500)."""
    rows = context.session.execute(
        text(f"""
            {ENTRY_SELECT}
            WHERE (CAST(:client AS uuid) IS NULL OR e.client_id = :client)
              AND (NOT :mine OR e.user_id = app.current_user_id())
              AND (CAST(:start AS date) IS NULL OR e.day >= :start)
              AND (CAST(:end AS date) IS NULL OR e.day <= :end)
            ORDER BY e.day DESC, e.created_at DESC
            LIMIT 500
        """),
        {"client": client_id, "mine": mine, "start": start, "end": end},
    ).mappings()
    return [TimeEntry.model_validate(dict(row)) for row in rows]


@router.post("/time", status_code=status.HTTP_201_CREATED)
def log_time(body: TimeEntryCreate, context: ReadDep) -> TimeEntry:
    """Logs the signed-in staff member's time for a client."""
    db = context.session
    ensure_not_erased(db, body.client_id)
    try:
        entry_id = db.execute(
            text("""
                INSERT INTO app.time_entries
                    (tenant_id, client_id, user_id, day, minutes, description, billable)
                VALUES (:tenant_id, :client_id, app.current_user_id(), :day, :minutes,
                        :description, :billable)
                RETURNING id
            """),
            {**body.model_dump(), "tenant_id": context.tenant_id},
        ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=422, detail="invalid_reference") from error
    return _entry(db, entry_id)


@router.patch("/time/{entry_id}")
def update_time(entry_id: UUID, body: TimeEntryUpdate, context: ReadDep) -> TimeEntry:
    _editable(context, entry_id)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if changes:
        assignments = ", ".join(f"{column} = :{column}" for column in changes)
        context.session.execute(
            text(f"UPDATE app.time_entries SET {assignments} WHERE id = :id"),
            {**changes, "id": entry_id},
        )
    return _entry(context.session, entry_id)


@router.delete("/time/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time(entry_id: UUID, context: ReadDep) -> None:
    _editable(context, entry_id)
    context.session.execute(text("DELETE FROM app.time_entries WHERE id = :id"), {"id": entry_id})


@router.get("/clients/{client_id}/retainer")
def get_retainer(client_id: UUID, context: ReadDep) -> Retainer | None:
    row = (
        context.session.execute(
            text("SELECT * FROM app.retainers WHERE client_id = :id"), {"id": client_id}
        )
        .mappings()
        .first()
    )
    return Retainer.model_validate(dict(row)) if row else None


@router.put("/clients/{client_id}/retainer")
def set_retainer(client_id: UUID, body: RetainerUpdate, context: SalesDep) -> Retainer:
    db = context.session
    ensure_not_erased(db, client_id)
    try:
        row = (
            db.execute(
                text("""
                    INSERT INTO app.retainers
                        (tenant_id, client_id, monthly_amount, included_minutes, hourly_rate,
                         currency, active)
                    SELECT :t, :c, :monthly_amount, :included_minutes, :hourly_rate,
                           t.currency, :active
                    FROM app.tenants t WHERE t.id = :t
                    ON CONFLICT (tenant_id, client_id) DO UPDATE
                    SET monthly_amount = excluded.monthly_amount,
                        included_minutes = excluded.included_minutes,
                        hourly_rate = excluded.hourly_rate, active = excluded.active,
                        updated_at = now()
                    RETURNING *
                """),
                {**body.model_dump(), "t": context.tenant_id, "c": client_id},
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:
        raise not_found() from error
    return Retainer.model_validate(dict(row))


def _hours(minutes: int) -> str:
    return f"{minutes / 60:.2f}".rstrip("0").rstrip(".")


MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def _month(value: str) -> tuple[dt.date, dt.date]:
    year, month = (int(part) for part in value.split("-"))
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def _words(db, tenant_id: UUID) -> dict[str, str]:
    """The bill's words in the business's language (the client reads them)."""
    locale = db.execute(
        text("SELECT locale FROM app.tenants WHERE id = :id"), {"id": tenant_id}
    ).scalar_one()
    return load_all_messages(locale if locale in ("he", "en") else "en")["bills"]


@dataclass
class _Draft:
    """A client's month as a bill, before it is written."""

    fee: int
    included: int
    rate: int
    worked: int
    extra: int
    lines: list[dict]
    entry_ids: list[UUID]

    @property
    def total(self) -> int:
        return sum(round(float(line["quantity"]) * line["unit_price"]) for line in self.lines)


def _draft(
    db, client_id: UUID, first: dt.date, last: dt.date, words: dict, *, lock: bool
) -> _Draft:
    """The retainer fee, and the month's unbilled billable time beyond the minutes it includes
    at its hourly rate (all of it when there is no fee)."""
    retainer = (
        db.execute(
            text("SELECT * FROM app.retainers WHERE client_id = :id AND active"),
            {"id": client_id},
        )
        .mappings()
        .first()
    )
    entries = db.execute(
        text(f"""
            SELECT id, minutes FROM app.time_entries
            WHERE client_id = :id AND billable AND bill_id IS NULL
              AND day BETWEEN :first AND :last
            {"FOR UPDATE" if lock else ""}
        """),
        {"id": client_id, "first": first, "last": last},
    ).all()
    worked = sum(e.minutes for e in entries)
    fee = retainer["monthly_amount"] if retainer else 0
    included = retainer["included_minutes"] if retainer else 0
    rate = retainer["hourly_rate"] if retainer else 0
    extra = max(worked - included, 0) if fee else worked
    period = f"{first.month:02d}/{first.year}"
    lines: list[dict] = []
    if fee:
        lines.append(
            {
                "description": words["retainer"].replace("{month}", period),
                "quantity": 1,
                "unit_price": fee,
            }
        )
    if extra and rate:
        lines.append(
            {
                "description": words["hoursBeyond" if fee else "hours"].replace("{month}", period),
                "quantity": _hours(extra),
                "unit_price": rate,
            }
        )
    return _Draft(fee, included, rate, worked, extra, lines, [e.id for e in entries])


def _write_bill(
    context: TenantContext, client_id: UUID, first: dt.date, last: dt.date, draft: _Draft, words
) -> UUID:
    db = context.session
    title = words["title"].replace("{month}", f"{first.month:02d}/{first.year}")
    bill_id = db.execute(
        text("""
            INSERT INTO app.quotes
                (tenant_id, client_id, number, kind, title, status, currency, deposit_percent,
                 period_start, period_end, sent_at, accepted_at, created_by)
            SELECT :t, :c, app.next_quote_number(), 'bill', :title, 'accepted', t.currency, 100,
                   :first, :last, now(), now(), app.current_user_id()
            FROM app.tenants t WHERE t.id = :t
            RETURNING id
        """),
        {"t": context.tenant_id, "c": client_id, "title": title, "first": first, "last": last},
    ).scalar_one()
    db.execute(
        text("""
            INSERT INTO app.quote_lines
                (tenant_id, quote_id, position, description, quantity, unit_price)
            VALUES (:t, :q, :position, :description, :quantity, :unit_price)
        """),
        [
            {"t": context.tenant_id, "q": bill_id, "position": i, **line}
            for i, line in enumerate(draft.lines)
        ],
    )
    if draft.entry_ids:
        db.execute(
            text("UPDATE app.time_entries SET bill_id = :bill WHERE id = ANY(:ids)"),
            {"bill": bill_id, "ids": draft.entry_ids},
        )
    return bill_id


@router.post("/clients/{client_id}/bills", status_code=status.HTTP_201_CREATED)
def bill_month(client_id: UUID, body: BillRequest, context: SalesDep) -> Quote:
    """Bills a client's month: the retainer fee, and the unbilled billable time of the month
    beyond the minutes it includes at its hourly rate (all of it when there is no fee)."""
    db = context.session
    ensure_not_erased(db, client_id)
    first, last = _month(body.month)
    words = _words(db, context.tenant_id)
    draft = _draft(db, client_id, first, last, words, lock=True)
    if not draft.lines:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="nothing_to_bill")
    return _load(db, _write_bill(context, client_id, first, last, draft, words))


class BillPreview(BaseModel):
    client_id: UUID
    client_name: str
    monthly_amount: int
    included_minutes: int
    worked_minutes: int = Field(description="Unbilled billable minutes in the month")
    extra_minutes: int = Field(description="Billed at the hourly rate")
    hourly_rate: int
    total: int
    currency: str
    billed: bool = Field(description="The month already has a bill for this client")


class BillingRun(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")
    client_ids: list[UUID] = Field(min_length=1, max_length=500)


class BillingRunResult(BaseModel):
    bills: list[Quote]
    skipped: list[UUID] = Field(description="Already billed for the month, or nothing to bill")


def _candidates(db, first: dt.date, last: dt.date) -> list[dict]:
    """Clients with an active retainer or unbilled billable time in the month."""
    rows = db.execute(
        text("""
            SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name,
                   EXISTS (
                       SELECT 1 FROM app.quotes q
                       WHERE q.client_id = c.id AND q.kind = 'bill' AND q.period_start = :first
                   ) AS billed
            FROM app.clients c
            WHERE c.erased_at IS NULL AND (
                EXISTS (SELECT 1 FROM app.retainers r WHERE r.client_id = c.id AND r.active)
                OR EXISTS (
                    SELECT 1 FROM app.time_entries e
                    WHERE e.client_id = c.id AND e.billable AND e.bill_id IS NULL
                      AND e.day BETWEEN :first AND :last
                )
            )
            ORDER BY c.first_name, c.last_name
        """),
        {"first": first, "last": last},
    ).mappings()
    return [dict(row) for row in rows]


@router.get("/bills/preview")
def billing_preview(
    context: SalesDep,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")],
) -> list[BillPreview]:
    """What billing the month would bill each client, before billing anyone."""
    db = context.session
    first, last = _month(month)
    words = _words(db, context.tenant_id)
    currency = db.execute(
        text("SELECT currency FROM app.tenants WHERE id = :id"), {"id": context.tenant_id}
    ).scalar_one()
    previews = []
    for client in _candidates(db, first, last):
        draft = _draft(db, client["id"], first, last, words, lock=False)
        previews.append(
            BillPreview(
                client_id=client["id"],
                client_name=client["name"],
                monthly_amount=draft.fee,
                included_minutes=draft.included,
                worked_minutes=draft.worked,
                extra_minutes=draft.extra if draft.rate else 0,
                hourly_rate=draft.rate,
                total=draft.total,
                currency=currency,
                billed=client["billed"],
            )
        )
    return previews


@router.post("/bills/run")
def billing_run(body: BillingRun, context: SalesDep) -> BillingRunResult:
    """Bills the month for the chosen clients at once. A client the month was already billed
    for, or with nothing to bill, is skipped (bill them one by one from their card if needed)."""
    db = context.session
    first, last = _month(body.month)
    words = _words(db, context.tenant_id)
    eligible = {c["id"]: c for c in _candidates(db, first, last)}
    bills, skipped = [], []
    for client_id in dict.fromkeys(body.client_ids):
        candidate = eligible.get(client_id)
        draft = (
            _draft(db, client_id, first, last, words, lock=True)
            if candidate and not candidate["billed"]
            else None
        )
        if draft is None or not draft.lines:
            skipped.append(client_id)
            continue
        bills.append(_load(db, _write_bill(context, client_id, first, last, draft, words)))
    return BillingRunResult(bills=bills, skipped=skipped)
