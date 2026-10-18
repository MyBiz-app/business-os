"""Plans (the catalog of memberships and punch cards) and entitlements (clients' purchases)."""

import datetime as dt
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import (
    RemoveResult,
    blank_to_none,
    delete_or_archive,
    ensure_not_erased,
    not_found,
    set_clause,
)
from app.api.deps import TenantContext, require
from app.api.pagination import MAX_LIMIT, FullPageDep, Page
from app.core.permissions import Permission

router = APIRouter(tags=["plans"])

CatalogReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
CatalogWriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]
CatalogDeleteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_DELETE))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]

PlanKind = Literal["membership", "punch_card"]
BillingCycle = Literal["monthly", "quarterly", "yearly", "custom"]
PeriodUnit = Literal["week", "month"]
MAX_FREEZE_DAYS = 90
# The length of a plan with a billing cycle: what the entitlement is valid for before the next
# charge (a custom cycle says its own days).
CYCLE_VALIDITY_DAYS = {"monthly": 30, "quarterly": 91, "yearly": 365}

PLAN_COLUMNS = (
    "id, name, description, kind, price_amount, price_currency, validity_days, credits, active, "
    "billing_cycle, billing_cycle_days, auto_renew, period_quota, period_unit, created_at, "
    "updated_at"
)


class PlanFields(BaseModel):
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description", mode="before")
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return blank_to_none(value)


class PlanCreate(PlanFields):
    name: str = Field(min_length=1, max_length=120)
    kind: PlanKind
    price_amount: int = Field(ge=0, description="Price in minor units (agorot, cents)")
    price_currency: str | None = Field(
        default=None, pattern=r"^[A-Z]{3}$", description="Defaults to the business currency"
    )
    validity_days: int = Field(ge=1, le=1095)
    credits: int | None = Field(default=None, ge=1, le=1000, description="Punch cards only")
    active: bool = True
    billing_cycle: BillingCycle | None = Field(
        default=None,
        description="Memberships only: how often it is billed. With a cycle, validity_days "
        "follows it (30, 91, 365 or billing_cycle_days)",
    )
    billing_cycle_days: int | None = Field(
        default=None, ge=1, le=1095, description="Only for the custom cycle"
    )
    auto_renew: bool = Field(default=False, description="Needs a billing cycle")
    period_quota: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Memberships only: visits allowed per period (for example 2 per week)",
    )
    period_unit: PeriodUnit | None = Field(default=None, description="With period_quota")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def credits_match_kind(self) -> "PlanCreate":
        if (self.kind == "punch_card") != (self.credits is not None):
            raise ValueError("punch cards need credits; memberships must not have credits")
        if (self.period_quota is None) != (self.period_unit is None):
            raise ValueError("period_quota and period_unit go together")
        if self.period_quota is not None and self.kind != "membership":
            raise ValueError("only memberships have a quota per period")
        if self.billing_cycle is None:
            if self.billing_cycle_days is not None or self.auto_renew:
                raise ValueError("a billing cycle is needed for renewing or cycle days")
            return self
        if self.kind != "membership":
            raise ValueError("only memberships have a billing cycle")
        if (self.billing_cycle == "custom") != (self.billing_cycle_days is not None):
            raise ValueError("billing_cycle_days goes with the custom cycle, and only with it")
        self.validity_days = self.billing_cycle_days or CYCLE_VALIDITY_DAYS[self.billing_cycle]
        return self


class PlanUpdate(PlanFields):
    """The kind and credits are fixed once a plan exists; create a new plan instead."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    price_amount: int | None = Field(default=None, ge=0)
    validity_days: int | None = Field(default=None, ge=1, le=1095)
    active: bool | None = None
    auto_renew: bool | None = Field(default=None, description="Needs a billing cycle")
    period_quota: int | None = Field(default=None, ge=1, le=100, description="Memberships only")
    period_unit: PeriodUnit | None = None

    @model_validator(mode="after")
    def quota_goes_with_unit(self) -> "PlanUpdate":
        fields = self.model_fields_set
        if ("period_quota" in fields) != ("period_unit" in fields) or (
            (self.period_quota is None) != (self.period_unit is None)
        ):
            raise ValueError("period_quota and period_unit go together (both or neither)")
        return self


class Plan(BaseModel):
    id: UUID
    name: str
    description: str | None
    kind: PlanKind
    price_amount: int
    price_currency: str
    validity_days: int
    credits: int | None
    active: bool
    billing_cycle: BillingCycle | None
    billing_cycle_days: int | None
    auto_renew: bool
    period_quota: int | None = Field(description="Visits allowed per period, if limited")
    period_unit: PeriodUnit | None
    created_at: datetime
    updated_at: datetime


class PlanListItem(Plan):
    """A plan in the catalog list, with how it sells (counts only, no money)."""

    holders: int = Field(description="Clients holding this plan valid today (current branch)")
    sold_last_30_days: int


EntitlementState = Literal["active", "upcoming", "frozen", "used_up", "expired", "cancelled"]


class Freeze(BaseModel):
    id: UUID
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None
    request_id: UUID | None = Field(description="The client's request, if it came from one")
    billing_mode: Literal["none", "defer", "credit"] = Field(
        description="What it did to the billing: deferred the next charge, credited it, or neither"
    )
    billing_shift_days: int = Field(description="Days the next charge moved")
    credit_amount: int = Field(description="Credit for the next charge, in minor units")
    fee_amount: int = Field(description="Freeze fee for the next charge, in minor units")


class Entitlement(BaseModel):
    id: UUID
    client_id: UUID
    plan_id: UUID
    name: str
    kind: PlanKind
    credits: int | None
    credits_used: int
    credits_remaining: int | None
    starts_on: dt.date
    ends_on: dt.date
    state: EntitlementState
    price_amount: int
    price_currency: str
    freezes: list[Freeze]
    created_at: datetime
    receipt_id: UUID | None = Field(description="The receipt of the payment for this plan")
    receipt_number: int | None
    billing_cycle: BillingCycle | None
    billing_cycle_days: int | None
    auto_renew: bool
    next_billing_on: dt.date | None = Field(description="Renewing memberships: the next charge")
    next_billing_amount: int | None = Field(
        description="What the next charge will be after freeze credits and fees (minor units)"
    )
    freezable: bool = Field(description="A membership that is not over, cancelled or used up")
    period_quota: int | None = Field(description="Visits allowed per week or month, if limited")
    period_unit: PeriodUnit | None
    period_used: int | None = Field(description="Visits counted in the current week or month")


PaymentMethod = Literal["card", "cash", "transfer", "other"]


class Sale(BaseModel):
    plan_id: UUID
    method: PaymentMethod = "card"
    starts_on: dt.date | None = Field(default=None, description="Defaults to today (local)")
    idempotency_key: str = Field(
        min_length=8, max_length=80, description="Same key, same sale: retries never double-sell"
    )


class FreezeCreate(BaseModel):
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def bounded(self) -> "FreezeCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on is before starts_on")
        if (self.ends_on - self.starts_on).days + 1 > MAX_FREEZE_DAYS:
            raise ValueError(f"a freeze can last at most {MAX_FREEZE_DAYS} days")
        return self


# Bookings that use up a credit: everything except a cancellation made in time.
# A visit given back by a manager, or a late cancellation or no-show the business only records
# (migration 0136), is not used up.
CREDIT_USED = "((b.status <> 'cancelled' OR b.late_cancel) AND NOT b.credit_released)"

ENTITLEMENT_SELECT = f"""
    SELECT e.id, e.client_id, e.plan_id, e.name, e.kind, e.credits, e.starts_on, e.ends_on,
           e.status, e.price_amount, e.price_currency, e.created_at,
           e.billing_cycle, e.billing_cycle_days, e.auto_renew, e.next_billing_on,
           e.billing_adjustment, e.period_quota, e.period_unit, used.count AS credits_used,
           CASE WHEN e.period_unit IS NOT NULL THEN
               app.quota_used(e.id, (now() AT TIME ZONE t.time_zone)::date)
           END AS period_used,
           (now() AT TIME ZONE t.time_zone)::date AS today,
           coalesce((
               SELECT json_agg(json_build_object(
                   'id', f.id, 'starts_on', f.starts_on, 'ends_on', f.ends_on, 'reason', f.reason,
                   'request_id', f.request_id, 'billing_mode', f.billing_mode,
                   'billing_shift_days', f.billing_shift_days, 'credit_amount', f.credit_amount,
                   'fee_amount', f.fee_amount
               ) ORDER BY f.starts_on)
               FROM app.entitlement_freezes f WHERE f.entitlement_id = e.id
           ), '[]') AS freezes,
           receipt.id AS receipt_id, receipt.number AS receipt_number
    FROM app.entitlements e
    JOIN app.tenants t ON t.id = e.tenant_id
    LEFT JOIN LATERAL (
        SELECT r.id, r.number FROM app.receipts r
        WHERE r.entitlement_id = e.id ORDER BY r.number LIMIT 1
    ) receipt ON true
    CROSS JOIN LATERAL (
        SELECT count(*)::int AS count FROM app.bookings b
        WHERE b.entitlement_id = e.id AND {CREDIT_USED}
    ) used
"""


def to_entitlement(row: Any) -> Entitlement:
    data = dict(row)
    today: dt.date = data.pop("today")
    status_ = data.pop("status")
    credits, used = data["credits"], data["credits_used"]
    data["credits_remaining"] = None if credits is None else max(credits - used, 0)
    freezes = [Freeze.model_validate(f) for f in data["freezes"]]
    if status_ == "cancelled":
        state: EntitlementState = "cancelled"
    elif data["ends_on"] < today:
        state = "expired"
    elif data["credits_remaining"] == 0:
        state = "used_up"
    elif data["starts_on"] > today:
        state = "upcoming"
    elif any(f.starts_on <= today <= f.ends_on for f in freezes):
        state = "frozen"
    else:
        state = "active"
    data["state"] = state
    adjustment = data.pop("billing_adjustment")
    data["next_billing_amount"] = (
        max(data["price_amount"] - adjustment, 0)
        if data["auto_renew"] and data["next_billing_on"] is not None
        else None
    )
    data["freezable"] = data["kind"] == "membership" and state in ("active", "upcoming", "frozen")
    return Entitlement.model_validate(data)


def issue_receipts_now(db: Session) -> None:
    """Receipts are issued when the transaction commits (migration 0025); this issues them
    right away, once the payment is linked to its plan, so the response can include them."""
    db.execute(text("SET CONSTRAINTS app.payments_issue_receipt IMMEDIATE"))


def load_entitlement(db: Session, entitlement_id: UUID) -> Entitlement:
    row = (
        db.execute(text(f"{ENTITLEMENT_SELECT} WHERE e.id = :id"), {"id": entitlement_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return to_entitlement(row)


def list_entitlements(db: Session, client_id: UUID, page: Page | None = None) -> list[Entitlement]:
    rows = db.execute(
        text(f"""
            {ENTITLEMENT_SELECT}
            WHERE e.client_id = :client_id
            ORDER BY e.status = 'cancelled', e.ends_on DESC, e.created_at DESC, e.id
            LIMIT :limit OFFSET :offset
        """),
        {
            "client_id": client_id,
            "limit": page.limit if page else MAX_LIMIT,
            "offset": page.offset if page else 0,
        },
    ).mappings()
    return [to_entitlement(row) for row in rows]


def usable_entitlement(db: Session, client_id: UUID, session_id: UUID) -> UUID | None:
    """The entitlement a booking into this session should use: valid on the session's local
    date, not frozen, with a credit left. Unlimited memberships first, then the card that
    expires soonest. Serialized per client, so two bookings never take the same last credit.
    Reservations of a court or room (migration 0044) never use a plan."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:id AS text), 0))"),
        {"id": client_id},
    )
    return db.execute(
        text(f"""
            WITH day AS (
                SELECT (s.starts_at AT TIME ZONE t.time_zone)::date AS value
                FROM app.sessions s JOIN app.tenants t ON t.id = s.tenant_id
                WHERE s.id = :session_id AND NOT s.reserved  -- reservations are paid by the hour
            )
            SELECT e.id FROM app.entitlements e, day
            WHERE e.client_id = :client_id AND e.status = 'active'
              AND day.value BETWEEN e.starts_on AND e.ends_on
              AND NOT EXISTS (
                  SELECT 1 FROM app.entitlement_freezes f
                  WHERE f.entitlement_id = e.id AND day.value BETWEEN f.starts_on AND f.ends_on
              )
              AND (e.credits IS NULL OR e.credits > (
                  SELECT count(*) FROM app.bookings b
                  WHERE b.entitlement_id = e.id AND {CREDIT_USED}
              ))
              AND (e.period_quota IS NULL OR e.period_quota > app.quota_used(e.id, day.value))
            ORDER BY e.credits IS NOT NULL, e.ends_on, e.created_at
            LIMIT 1
        """),
        {"client_id": client_id, "session_id": session_id},
    ).scalar()


def quota_reached(db: Session, client_id: UUID, session_id: UUID) -> bool:
    """The client has a plan valid for this session's day whose visits for the week or month
    are all used (so the booking cannot use it, though the plan itself is fine)."""
    return bool(
        db.execute(
            text("""
                WITH day AS (
                    SELECT (s.starts_at AT TIME ZONE t.time_zone)::date AS value
                    FROM app.sessions s JOIN app.tenants t ON t.id = s.tenant_id
                    WHERE s.id = :session_id
                )
                SELECT EXISTS (
                    SELECT 1 FROM app.entitlements e, day
                    WHERE e.client_id = :client_id AND e.status = 'active'
                      AND day.value BETWEEN e.starts_on AND e.ends_on
                      AND e.period_quota IS NOT NULL
                      AND e.period_quota <= app.quota_used(e.id, day.value)
                )
            """),
            {"client_id": client_id, "session_id": session_id},
        ).scalar()
    )


# --- Plans ------------------------------------------------------------------------------------


@router.get("/plans")
def list_plans(
    context: CatalogReadDep, active: Annotated[bool | None, Query()] = None
) -> list[PlanListItem]:
    where, params = (
        ("WHERE p.active = :active", {"active": active}) if active is not None else ("", {})
    )
    # One pass over the entitlements for all plans; "today" in the business's time zone.
    columns = ", ".join(f"p.{column.strip()}" for column in PLAN_COLUMNS.split(","))
    rows = context.session.execute(
        text(f"""
            WITH today AS (
                SELECT (now() AT TIME ZONE time_zone)::date AS day
                FROM app.tenants WHERE id = app.current_tenant_id()
            ), sales AS (
                SELECT e.plan_id,
                       count(*) FILTER (
                           WHERE e.status = 'active' AND today.day BETWEEN e.starts_on AND e.ends_on
                       ) AS holders,
                       count(*) FILTER (
                           WHERE e.created_at > now() - interval '30 days'
                       ) AS sold_last_30_days
                FROM app.entitlements e CROSS JOIN today
                WHERE e.location_id IS NULL OR app.in_branch(e.location_id)
                GROUP BY e.plan_id
            )
            SELECT {columns}, coalesce(s.holders, 0) AS holders,
                   coalesce(s.sold_last_30_days, 0) AS sold_last_30_days
            FROM app.plans p LEFT JOIN sales s ON s.plan_id = p.id {where}
            ORDER BY p.active DESC, p.kind, p.price_amount DESC, p.name
        """),
        params,
    ).mappings()
    return [PlanListItem.model_validate(dict(row)) for row in rows]


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanCreate, context: CatalogWriteDep) -> Plan:
    row = (
        context.session.execute(
            text(f"""
                INSERT INTO app.plans
                    (tenant_id, name, description, kind, price_amount, price_currency,
                     validity_days, credits, active, billing_cycle, billing_cycle_days, auto_renew,
                     period_quota, period_unit)
                SELECT :tenant_id, :name, :description, :kind, :price_amount,
                       coalesce(:price_currency, t.currency), :validity_days, :credits, :active,
                       :billing_cycle, :billing_cycle_days, :auto_renew, :period_quota,
                       :period_unit
                FROM app.tenants t WHERE t.id = :tenant_id
                RETURNING {PLAN_COLUMNS}
            """),
            {**body.model_dump(), "tenant_id": context.tenant_id},
        )
        .mappings()
        .one()
    )
    return Plan.model_validate(dict(row))


@router.get("/plans/{plan_id}")
def get_plan(plan_id: UUID, context: CatalogReadDep) -> Plan:
    row = (
        context.session.execute(
            text(f"SELECT {PLAN_COLUMNS} FROM app.plans WHERE id = :id"), {"id": plan_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Plan.model_validate(dict(row))


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: UUID, body: PlanUpdate, context: CatalogWriteDep) -> Plan:
    """Changes apply to future sales only; sold entitlements keep their own terms."""
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None or key in ("description", "period_quota", "period_unit")
    }
    if changes.get("period_quota") is not None:
        kind = context.session.execute(
            text("SELECT kind FROM app.plans WHERE id = :id"), {"id": plan_id}
        ).scalar()
        if kind is not None and kind != "membership":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_a_membership")
    if changes.get("auto_renew"):
        has_cycle = context.session.execute(
            text("SELECT billing_cycle IS NOT NULL FROM app.plans WHERE id = :id"), {"id": plan_id}
        ).scalar()
        if has_cycle is False:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_billing_cycle")
    row = (
        context.session.execute(
            text(f"""
                UPDATE app.plans SET {set_clause(changes, PlanUpdate.model_fields)} WHERE id = :id
                RETURNING {PLAN_COLUMNS}
            """),
            {**changes, "id": plan_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Plan.model_validate(dict(row))


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: UUID, context: CatalogDeleteDep) -> RemoveResult:
    """Removes a membership or punch card nobody bought; a sold one is archived (hidden)."""
    return delete_or_archive(context.session, "plans", plan_id)


# --- Entitlements -----------------------------------------------------------------------------


@router.get("/clients/{client_id}/entitlements")
def client_entitlements(
    client_id: UUID, context: ClientsReadDep, page: FullPageDep
) -> list[Entitlement]:
    return list_entitlements(context.session, client_id, page)


@router.post("/clients/{client_id}/entitlements", status_code=status.HTTP_201_CREATED)
def sell_plan(client_id: UUID, body: Sale, context: SalesDep) -> Entitlement:
    """Sells a plan to a client. Payment is simulated until a payment provider is connected."""
    db = context.session
    ensure_not_erased(db, client_id)
    payment_id = db.execute(
        text("""
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, method,
                 idempotency_key, created_by)
            SELECT :tenant_id, c.id, p.price_amount, p.price_currency, 'succeeded', 'simulated',
                   :method, :key, app.current_user_id()
            FROM app.plans p, app.clients c
            WHERE p.id = :plan_id AND p.active AND c.id = :client_id
            ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
            RETURNING id
        """),
        {
            "tenant_id": context.tenant_id,
            "plan_id": body.plan_id,
            "client_id": client_id,
            "key": body.idempotency_key,
            "method": body.method,
        },
    ).scalar()
    if payment_id is None:
        existing = db.execute(
            text("SELECT entitlement_id FROM app.payments WHERE idempotency_key = :key"),
            {"key": body.idempotency_key},
        ).scalar()
        if existing is None:  # no such plan or client (nothing was inserted)
            raise HTTPException(status_code=422, detail="invalid_reference")
        return load_entitlement(db, existing)

    entitlement_id = db.execute(
        text("""
            INSERT INTO app.entitlements
                (tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
                 price_amount, price_currency, sold_by, billing_cycle, billing_cycle_days,
                 auto_renew, next_billing_on)
            SELECT p.tenant_id, :client_id, p.id, p.name, p.kind, p.credits, start.value,
                   start.value + p.validity_days - 1, p.price_amount, p.price_currency,
                   app.current_user_id(), p.billing_cycle, p.billing_cycle_days, p.auto_renew,
                   CASE WHEN p.auto_renew THEN start.value + p.validity_days END
            FROM app.plans p
            JOIN app.tenants t ON t.id = p.tenant_id
            CROSS JOIN LATERAL (
                SELECT coalesce(CAST(:starts_on AS date), (now() AT TIME ZONE t.time_zone)::date)
                    AS value
            ) start
            WHERE p.id = :plan_id
            RETURNING id
        """),
        {"client_id": client_id, "plan_id": body.plan_id, "starts_on": body.starts_on},
    ).scalar_one()
    db.execute(
        text("UPDATE app.payments SET entitlement_id = :entitlement_id WHERE id = :id"),
        {"entitlement_id": entitlement_id, "id": payment_id},
    )
    issue_receipts_now(db)
    return load_entitlement(db, entitlement_id)


@router.post("/entitlements/{entitlement_id}/freezes", status_code=status.HTTP_201_CREATED)
def freeze_entitlement(entitlement_id: UUID, body: FreezeCreate, context: SalesDep) -> Entitlement:
    """Pauses the entitlement for the given days and extends its end date by as many days."""
    db = context.session
    current = load_entitlement(db, entitlement_id)
    if current.kind != "membership":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_a_membership")
    if current.state in ("cancelled", "expired"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_active")
    if body.starts_on < current.starts_on or body.starts_on > current.ends_on:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="outside_validity")
    if any(f.starts_on <= body.ends_on and body.starts_on <= f.ends_on for f in current.freezes):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="overlapping_freeze")

    db.execute(
        text("""
            SELECT app.apply_freeze(:id, :starts_on, :ends_on, :reason, NULL, false, false, NULL)
        """),
        {**body.model_dump(), "id": entitlement_id},
    )
    return load_entitlement(db, entitlement_id)


@router.post("/entitlements/{entitlement_id}/cancel")
def cancel_entitlement(entitlement_id: UUID, context: SalesDep) -> Entitlement:
    """Stops the entitlement from being used for new bookings (no refund is simulated)."""
    updated = context.session.execute(
        text("""
            UPDATE app.entitlements
            SET status = 'cancelled', cancelled_at = now(), updated_at = now()
            WHERE id = :id
            RETURNING id
        """),
        {"id": entitlement_id},
    ).scalar()
    if updated is None:
        raise not_found()
    return load_entitlement(context.session, entitlement_id)
