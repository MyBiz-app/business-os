"""Freezing a membership: the business's rules, a client's request from the app, the manager's
decision, and ending a freeze early.

A freeze pauses a membership for a range of days. For one that is paid in advance the end date
moves by the same number of days. For a renewing one the next charge moves too (or, if the
business chose so, the next charge is credited by the frozen days). The arithmetic lives in the
database (migration 0134: `freeze_effect`, `apply_freeze`, `end_freeze_early`) so a preview, a
manager's decision and an automatic approval can never disagree."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import (
    ClientDep,
    TenantContext,
    TenantDep,
    UserDep,
    ensure_branch_visible,
    require,
)
from app.api.plans import Entitlement, load_entitlement
from app.core.audit import record
from app.core.permissions import Permission
from app.messaging.notifications import notify

router = APIRouter(tags=["plans"])
client_router = APIRouter(prefix="/client", tags=["client"])

SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]
SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

Reason = Literal["travel", "reserve_duty", "illness", "pregnancy", "other"]
RequestStatus = Literal["pending", "approved", "rejected", "cancelled"]
BillingMode = Literal["defer", "credit"]
REASONS: tuple[str, ...] = ("travel", "reserve_duty", "illness", "pregnancy", "other")


class FreezeRules(BaseModel):
    allow_requests: bool = Field(default=False, description="Clients may ask from the app")
    min_days: int = Field(default=1, ge=1, le=90)
    max_days: int = Field(default=30, ge=1, le=90)
    yearly_bank_days: int | None = Field(
        default=None,
        ge=1,
        le=366,
        description="Most freeze days per client in a year; empty: no limit",
    )
    notice_days: int = Field(
        default=0, ge=0, le=60, description="Days ahead a request must be sent"
    )
    fee_amount: int = Field(default=0, ge=0, description="Freeze fee in minor units")
    billing_mode: BillingMode = Field(
        default="defer", description="Renewing memberships: defer the next charge, or credit it"
    )
    auto_approve_reasons: list[Reason] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self) -> "FreezeRules":
        if self.max_days < self.min_days:
            raise ValueError("max_days must not be below min_days")
        return self


class FreezeBank(BaseModel):
    year: int
    yearly_bank_days: int | None
    used_days: int = Field(description="Freeze days this year, including requests waiting")
    remaining_days: int | None


class ClientFreezeRules(BaseModel):
    rules: FreezeRules
    bank: FreezeBank


class FreezeRequestCreate(BaseModel):
    starts_on: dt.date
    ends_on: dt.date
    reason: Reason
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def ordered(self) -> "FreezeRequestCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on is before starts_on")
        if (self.ends_on - self.starts_on).days > 90:
            raise ValueError("a freeze can last at most 90 days")
        return self


class FreezePreview(BaseModel):
    days: int
    new_ends_on: dt.date = Field(description="The membership's end date once frozen")
    billing_mode: Literal["none", "defer", "credit"]
    next_billing_from: dt.date | None
    next_billing_to: dt.date | None
    credit_amount: int
    fee_amount: int
    next_billing_amount_after: int | None = Field(
        description="The next charge after this freeze (renewing memberships)"
    )
    problems: list[str] = Field(
        description="Why a request would be refused now: freeze_requests_off, not_freezable, "
        "too_short, too_long, notice_required, outside_validity, overlapping_freeze, "
        "overlapping_request, bank_exceeded"
    )
    auto_approved: bool = Field(description="Whether it would be approved without a manager")


class FreezeRequest(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str
    entitlement_id: UUID
    entitlement_name: str
    starts_on: dt.date
    ends_on: dt.date
    reason: Reason
    note: str | None
    status: RequestStatus
    approved_starts_on: dt.date | None
    approved_ends_on: dt.date | None
    auto_approved: bool
    decided_by_name: str | None
    decided_at: dt.datetime | None
    decision_note: str | None
    created_at: dt.datetime
    days: int


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=500, description="Shown to the client")
    approved_ends_on: dt.date | None = Field(
        default=None, description="Approve only part of it: the last day to freeze"
    )

    @field_validator("note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


REQUEST_SELECT = """
    SELECT r.id, r.client_id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           r.entitlement_id, e.name AS entitlement_name, r.starts_on, r.ends_on, r.reason, r.note,
           r.status, r.approved_starts_on, r.approved_ends_on, r.auto_approved,
           coalesce(d.full_name, d.email) AS decided_by_name, r.decided_at, r.decision_note,
           r.created_at, (r.ends_on - r.starts_on + 1) AS days
    FROM app.freeze_requests r
    JOIN app.clients c ON c.id = r.client_id
    JOIN app.entitlements e ON e.id = r.entitlement_id
    LEFT JOIN app.users d ON d.id = r.decided_by
"""


def load_rules(db: Session, tenant_id: UUID | None = None) -> FreezeRules:
    row = (
        db.execute(
            text("""
                SELECT allow_requests, min_days, max_days, yearly_bank_days, notice_days,
                       fee_amount, billing_mode, auto_approve_reasons
                FROM app.tenant_freeze_rules WHERE tenant_id = app.acting_tenant_id()
            """)
        )
        .mappings()
        .first()
    )
    return FreezeRules.model_validate(dict(row)) if row else FreezeRules()


def local_today(db: Session) -> dt.date:
    return db.execute(
        text(
            "SELECT (now() AT TIME ZONE time_zone)::date FROM app.tenants"
            " WHERE id = app.acting_tenant_id()"
        )
    ).scalar_one()


def bank_for(db: Session, client_id: UUID, rules: FreezeRules, year: int) -> FreezeBank:
    """Freeze days of the client's memberships starting in the year, plus requests waiting."""
    used = db.execute(
        text("""
            SELECT coalesce(sum(f.ends_on - f.starts_on + 1), 0)
                 + coalesce((SELECT sum(r.ends_on - r.starts_on + 1)
                             FROM app.freeze_requests r
                             WHERE r.client_id = :client AND r.status = 'pending'
                               AND extract(year FROM r.starts_on) = :year), 0)
            FROM app.entitlement_freezes f JOIN app.entitlements e ON e.id = f.entitlement_id
            WHERE e.client_id = :client AND extract(year FROM f.starts_on) = :year
        """),
        {"client": client_id, "year": year},
    ).scalar_one()
    bank = rules.yearly_bank_days
    return FreezeBank(
        year=year,
        yearly_bank_days=bank,
        used_days=int(used),
        remaining_days=None if bank is None else max(bank - int(used), 0),
    )


def problems_with(
    db: Session,
    entitlement: Entitlement,
    rules: FreezeRules,
    starts_on: dt.date,
    ends_on: dt.date,
    today: dt.date,
) -> list[str]:
    """Everything wrong with asking for these days now (empty: the request would be accepted)."""
    problems: list[str] = []
    if not rules.allow_requests:
        problems.append("freeze_requests_off")
    if not entitlement.freezable:
        problems.append("not_freezable")
    days = (ends_on - starts_on).days + 1
    if days < rules.min_days:
        problems.append("too_short")
    if days > rules.max_days:
        problems.append("too_long")
    if starts_on < today + dt.timedelta(days=rules.notice_days):
        problems.append("notice_required")
    if starts_on < entitlement.starts_on or starts_on > entitlement.ends_on:
        problems.append("outside_validity")
    if any(f.starts_on <= ends_on and starts_on <= f.ends_on for f in entitlement.freezes):
        problems.append("overlapping_freeze")
    waiting = db.execute(
        text("""
            SELECT 1 FROM app.freeze_requests
            WHERE entitlement_id = :id AND status = 'pending'
              AND starts_on <= :ends AND ends_on >= :starts
        """),
        {"id": entitlement.id, "starts": starts_on, "ends": ends_on},
    ).first()
    if waiting is not None:
        problems.append("overlapping_request")
    if rules.yearly_bank_days is not None:
        bank = bank_for(db, entitlement.client_id, rules, starts_on.year)
        if bank.used_days + days > rules.yearly_bank_days:
            problems.append("bank_exceeded")
    return problems


def preview_for(
    db: Session, entitlement: Entitlement, rules: FreezeRules, starts_on: dt.date, ends_on: dt.date
) -> FreezePreview:
    effect = (
        db.execute(
            text("SELECT * FROM app.freeze_effect(:id, :starts, :ends)"),
            {"id": entitlement.id, "starts": starts_on, "ends": ends_on},
        )
        .mappings()
        .one()
    )
    today = local_today(db)
    problems = problems_with(db, entitlement, rules, starts_on, ends_on, today)
    after = None
    if entitlement.next_billing_amount is not None:
        after = max(
            entitlement.next_billing_amount + effect["credit_amount"] - effect["fee_amount"], 0
        )
    return FreezePreview(
        days=effect["days"],
        new_ends_on=effect["new_ends_on"],
        billing_mode=effect["billing_mode"],
        next_billing_from=effect["next_billing_from"] if entitlement.auto_renew else None,
        next_billing_to=effect["next_billing_to"] if entitlement.auto_renew else None,
        credit_amount=effect["credit_amount"],
        fee_amount=effect["fee_amount"],
        next_billing_amount_after=after,
        problems=problems,
        auto_approved=False,
    )


def _check_dates(starts_on: dt.date, ends_on: dt.date) -> None:
    if ends_on < starts_on or (ends_on - starts_on).days > 90:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bad_dates")


def _load_request(db: Session, request_id: UUID) -> FreezeRequest:
    row = (
        db.execute(text(REQUEST_SELECT + " WHERE r.id = :id"), {"id": request_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return FreezeRequest.model_validate(dict(row))


# --- The business's rules ---------------------------------------------------------------------


@router.get("/freeze-rules")
def get_freeze_rules(context: TenantDep) -> FreezeRules:
    return load_rules(context.session)


@router.put("/freeze-rules")
def set_freeze_rules(body: FreezeRules, context: SettingsDep) -> FreezeRules:
    context.session.execute(
        text("""
            INSERT INTO app.tenant_freeze_rules
                (tenant_id, allow_requests, min_days, max_days, yearly_bank_days, notice_days,
                 fee_amount, billing_mode, auto_approve_reasons)
            VALUES (:tenant_id, :allow_requests, :min_days, :max_days, :yearly_bank_days,
                    :notice_days, :fee_amount, :billing_mode, :auto_approve_reasons)
            ON CONFLICT (tenant_id) DO UPDATE SET
                allow_requests = EXCLUDED.allow_requests, min_days = EXCLUDED.min_days,
                max_days = EXCLUDED.max_days, yearly_bank_days = EXCLUDED.yearly_bank_days,
                notice_days = EXCLUDED.notice_days, fee_amount = EXCLUDED.fee_amount,
                billing_mode = EXCLUDED.billing_mode,
                auto_approve_reasons = EXCLUDED.auto_approve_reasons, updated_at = now()
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id},
    )
    record(context.session, "freeze_rules.update")
    return load_rules(context.session)


# --- The business's side ----------------------------------------------------------------------


@router.get("/entitlements/{entitlement_id}/freeze-preview")
def preview_freeze(
    entitlement_id: UUID,
    context: SalesDep,
    starts_on: Annotated[dt.date, Query()],
    ends_on: Annotated[dt.date, Query()],
) -> FreezePreview:
    """What freezing these days would do. A manager may freeze for any reason, so `problems`
    lists what a client's request would run into."""
    _check_dates(starts_on, ends_on)
    entitlement = load_entitlement(context.session, entitlement_id)
    return preview_for(
        context.session, entitlement, load_rules(context.session), starts_on, ends_on
    )


@router.get("/freeze-requests")
def list_freeze_requests(
    context: SalesDep,
    request_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[FreezeRequest]:
    """Waiting requests first, then the latest decided ones."""
    filters = "WHERE (e.location_id IS NULL OR app.in_branch(e.location_id))"
    params: dict[str, object] = {}
    if request_status is not None:
        filters += " AND r.status = :status"
        params["status"] = request_status
    if client_id is not None:
        filters += " AND r.client_id = :client"
        params["client"] = client_id
    if context.branches is not None:
        filters += " AND (e.location_id IS NULL OR e.location_id = ANY(CAST(:branches AS uuid[])))"
        params["branches"] = list(context.branches)
    rows = context.session.execute(
        text(
            REQUEST_SELECT + f" {filters}"
            " ORDER BY (r.status = 'pending') DESC, r.starts_on, r.created_at LIMIT 200"
        ),
        params,
    ).mappings()
    return [FreezeRequest.model_validate(dict(row)) for row in rows]


def _decide_context(db: Session, request_id: UUID, context: TenantContext) -> dict:
    row = (
        db.execute(
            text("""
                SELECT r.client_id, r.entitlement_id, r.starts_on, r.ends_on, r.reason, r.status,
                       e.location_id
                FROM app.freeze_requests r JOIN app.entitlements e ON e.id = r.entitlement_id
                WHERE r.id = :id FOR UPDATE OF r
            """),
            {"id": request_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row["location_id"])
    if row["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request_not_pending")
    return dict(row)


@router.post("/freeze-requests/{request_id}/approve")
def approve_freeze_request(
    request_id: UUID, body: Decision, user: UserDep, context: SalesDep
) -> FreezeRequest:
    """Approves the whole request, or only part of it (`approved_ends_on`)."""
    db = context.session
    current = _decide_context(db, request_id, context)
    ends_on = body.approved_ends_on or current["ends_on"]
    if ends_on < current["starts_on"] or ends_on > current["ends_on"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bad_dates")
    entitlement = load_entitlement(db, current["entitlement_id"])
    if not entitlement.freezable:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_freezable")
    if any(
        f.starts_on <= ends_on and current["starts_on"] <= f.ends_on for f in entitlement.freezes
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="overlapping_freeze")
    db.execute(
        text("SELECT app.apply_freeze(:e, :starts, :ends, :reason, :r, true, false, :note)"),
        {
            "e": current["entitlement_id"],
            "starts": current["starts_on"],
            "ends": ends_on,
            "reason": current["reason"],
            "r": request_id,
            "note": body.note,
        },
    )
    notify(
        db,
        context.tenant_id,
        [current["client_id"]],
        "freeze_approved",
        {
            "plan_name": entitlement.name,
            "starts_on": current["starts_on"].isoformat(),
            "ends_on": ends_on.isoformat(),
            "note": body.note,
        },
    )
    record(db, "freeze_request.approve", entity_type="freeze_request", entity_id=request_id)
    return _load_request(db, request_id)


@router.post("/freeze-requests/{request_id}/reject")
def reject_freeze_request(
    request_id: UUID, body: Decision, user: UserDep, context: SalesDep
) -> FreezeRequest:
    db = context.session
    current = _decide_context(db, request_id, context)
    db.execute(
        text("""
            UPDATE app.freeze_requests
            SET status = 'rejected', decided_by = :by, decided_at = now(), decision_note = :note
            WHERE id = :id
        """),
        {"by": user.id, "note": body.note, "id": request_id},
    )
    name = db.execute(
        text("SELECT name FROM app.entitlements WHERE id = :id"), {"id": current["entitlement_id"]}
    ).scalar_one()
    notify(
        db,
        context.tenant_id,
        [current["client_id"]],
        "freeze_rejected",
        {
            "plan_name": name,
            "starts_on": current["starts_on"].isoformat(),
            "ends_on": current["ends_on"].isoformat(),
            "note": body.note,
        },
    )
    record(db, "freeze_request.reject", entity_type="freeze_request", entity_id=request_id)
    return _load_request(db, request_id)


@router.post("/freezes/{freeze_id}/end-early")
def end_freeze_early(freeze_id: UUID, context: SalesDep) -> Entitlement:
    """The client is back: the freeze ends yesterday (or disappears if it has not begun)."""
    return _end_early(context.session, freeze_id)


def _end_early(db: Session, freeze_id: UUID) -> Entitlement:
    row = db.execute(
        text("SELECT entitlement_id, ends_on FROM app.entitlement_freezes WHERE id = :id"),
        {"id": freeze_id},
    ).first()
    if row is None:
        raise not_found()
    if row.ends_on < local_today(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="freeze_over")
    db.execute(text("SELECT app.end_freeze_early(:id)"), {"id": freeze_id})
    return load_entitlement(db, row.entitlement_id)


# --- The client's side ------------------------------------------------------------------------


def _my_entitlement(db: Session, entitlement_id: UUID) -> Entitlement:
    entitlement = load_entitlement(db, entitlement_id)  # clients only see their own (RLS)
    return entitlement


@client_router.get("/freeze-rules")
def my_freeze_rules(context: ClientDep) -> ClientFreezeRules:
    db = context.session
    rules = load_rules(db)
    return ClientFreezeRules(
        rules=rules, bank=bank_for(db, context.client_id, rules, local_today(db).year)
    )


@client_router.get("/entitlements/{entitlement_id}/freeze-preview")
def my_freeze_preview(
    entitlement_id: UUID,
    context: ClientDep,
    starts_on: Annotated[dt.date, Query()],
    ends_on: Annotated[dt.date, Query()],
    reason: Annotated[Reason | None, Query()] = None,
) -> FreezePreview:
    """Exactly what will happen, shown before the client sends the request."""
    _check_dates(starts_on, ends_on)
    db = context.session
    rules = load_rules(db)
    preview = preview_for(db, _my_entitlement(db, entitlement_id), rules, starts_on, ends_on)
    preview.auto_approved = (
        reason is not None and reason in rules.auto_approve_reasons and not preview.problems
    )
    return preview


@client_router.get("/freeze-requests")
def my_freeze_requests(context: ClientDep) -> list[FreezeRequest]:
    rows = context.session.execute(
        text(REQUEST_SELECT + " ORDER BY r.created_at DESC LIMIT 50")
    ).mappings()
    return [FreezeRequest.model_validate(dict(row)) for row in rows]


@client_router.post(
    "/entitlements/{entitlement_id}/freeze-requests", status_code=status.HTTP_201_CREATED
)
def ask_for_freeze(
    entitlement_id: UUID, body: FreezeRequestCreate, context: ClientDep
) -> FreezeRequest:
    """Sends the request to the client's branch managers; a reason the business approves
    automatically takes effect at once."""
    db = context.session
    rules = load_rules(db)
    entitlement = _my_entitlement(db, entitlement_id)
    problems = problems_with(db, entitlement, rules, body.starts_on, body.ends_on, local_today(db))
    if problems:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=problems[0])
    request_id = db.execute(
        text("""
            INSERT INTO app.freeze_requests
                (tenant_id, client_id, entitlement_id, starts_on, ends_on, reason, note)
            VALUES (app.acting_tenant_id(), app.current_client_id(), :e, :starts_on, :ends_on,
                    :reason, :note)
            RETURNING id
        """),
        {"e": entitlement_id, **body.model_dump()},
    ).scalar_one()
    if body.reason in rules.auto_approve_reasons:
        db.execute(
            text("SELECT app.apply_freeze(:e, :starts, :ends, :reason, :r, true, true, NULL)"),
            {
                "e": entitlement_id,
                "starts": body.starts_on,
                "ends": body.ends_on,
                "reason": body.reason,
                "r": request_id,
            },
        )
    return _load_request(db, request_id)


@client_router.delete("/freeze-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_freeze_request(request_id: UUID, context: ClientDep) -> None:
    cancelled = context.session.execute(
        text("""
            UPDATE app.freeze_requests SET status = 'cancelled'
            WHERE id = :id AND status = 'pending' RETURNING id
        """),
        {"id": request_id},
    ).scalar()
    if cancelled is None:
        raise not_found()


@client_router.post("/freezes/{freeze_id}/end-early")
def my_end_freeze_early(freeze_id: UUID, context: ClientDep) -> Entitlement:
    """ "I'm back early": the freeze ends yesterday, and the dates and the charge come back."""
    return _end_early(context.session, freeze_id)
