"""Plans (the catalog of memberships and punch cards) and entitlements (clients' purchases)."""

import datetime as dt
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(tags=["plans"])

CatalogReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
CatalogWriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]

PlanKind = Literal["membership", "punch_card"]
MAX_FREEZE_DAYS = 90

PLAN_COLUMNS = (
    "id, name, description, kind, price_amount, price_currency, validity_days, credits, active, "
    "created_at, updated_at"
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
        return self


class PlanUpdate(PlanFields):
    """The kind and credits are fixed once a plan exists; create a new plan instead."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    price_amount: int | None = Field(default=None, ge=0)
    validity_days: int | None = Field(default=None, ge=1, le=1095)
    active: bool | None = None


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
    created_at: datetime
    updated_at: datetime


EntitlementState = Literal["active", "upcoming", "frozen", "used_up", "expired", "cancelled"]


class Freeze(BaseModel):
    id: UUID
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None


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


class Sale(BaseModel):
    plan_id: UUID
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
CREDIT_USED = "(b.status <> 'cancelled' OR b.late_cancel)"

ENTITLEMENT_SELECT = f"""
    SELECT e.id, e.client_id, e.plan_id, e.name, e.kind, e.credits, e.starts_on, e.ends_on,
           e.status, e.price_amount, e.price_currency, e.created_at,
           used.count AS credits_used,
           (now() AT TIME ZONE t.time_zone)::date AS today,
           coalesce((
               SELECT json_agg(json_build_object(
                   'id', f.id, 'starts_on', f.starts_on, 'ends_on', f.ends_on, 'reason', f.reason
               ) ORDER BY f.starts_on)
               FROM app.entitlement_freezes f WHERE f.entitlement_id = e.id
           ), '[]') AS freezes
    FROM app.entitlements e
    JOIN app.tenants t ON t.id = e.tenant_id
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
    return Entitlement.model_validate(data)


def load_entitlement(db: Session, entitlement_id: UUID) -> Entitlement:
    row = (
        db.execute(text(f"{ENTITLEMENT_SELECT} WHERE e.id = :id"), {"id": entitlement_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return to_entitlement(row)


def list_entitlements(db: Session, client_id: UUID) -> list[Entitlement]:
    rows = db.execute(
        text(f"""
            {ENTITLEMENT_SELECT}
            WHERE e.client_id = :client_id
            ORDER BY e.status = 'cancelled', e.ends_on DESC, e.created_at DESC
        """),
        {"client_id": client_id},
    ).mappings()
    return [to_entitlement(row) for row in rows]


def usable_entitlement(db: Session, client_id: UUID, session_id: UUID) -> UUID | None:
    """The entitlement a booking into this session should use: valid on the session's local
    date, not frozen, with a credit left. Unlimited memberships first, then the card that
    expires soonest. Serialized per client, so two bookings never take the same last credit."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:id AS text), 0))"),
        {"id": client_id},
    )
    return db.execute(
        text(f"""
            WITH day AS (
                SELECT (s.starts_at AT TIME ZONE t.time_zone)::date AS value
                FROM app.sessions s JOIN app.tenants t ON t.id = s.tenant_id
                WHERE s.id = :session_id
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
            ORDER BY e.credits IS NOT NULL, e.ends_on, e.created_at
            LIMIT 1
        """),
        {"client_id": client_id, "session_id": session_id},
    ).scalar()


# --- Plans ------------------------------------------------------------------------------------


@router.get("/plans")
def list_plans(
    context: CatalogReadDep, active: Annotated[bool | None, Query()] = None
) -> list[Plan]:
    where, params = (
        ("WHERE active = :active", {"active": active}) if active is not None else ("", {})
    )
    rows = context.session.execute(
        text(f"""
            SELECT {PLAN_COLUMNS} FROM app.plans {where}
            ORDER BY active DESC, kind, price_amount DESC, name
        """),
        params,
    ).mappings()
    return [Plan.model_validate(dict(row)) for row in rows]


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanCreate, context: CatalogWriteDep) -> Plan:
    row = (
        context.session.execute(
            text(f"""
                INSERT INTO app.plans
                    (tenant_id, name, description, kind, price_amount, price_currency,
                     validity_days, credits, active)
                SELECT :tenant_id, :name, :description, :kind, :price_amount,
                       coalesce(:price_currency, t.currency), :validity_days, :credits, :active
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
        if value is not None or key == "description"
    }
    row = (
        context.session.execute(
            text(f"""
                UPDATE app.plans SET {set_clause(changes)} WHERE id = :id
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


# --- Entitlements -----------------------------------------------------------------------------


@router.get("/clients/{client_id}/entitlements")
def client_entitlements(client_id: UUID, context: ClientsReadDep) -> list[Entitlement]:
    return list_entitlements(context.session, client_id)


@router.post("/clients/{client_id}/entitlements", status_code=status.HTTP_201_CREATED)
def sell_plan(client_id: UUID, body: Sale, context: SalesDep) -> Entitlement:
    """Sells a plan to a client. Payment is simulated until a payment provider is connected."""
    db = context.session
    payment_id = db.execute(
        text("""
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, idempotency_key,
                 created_by)
            SELECT :tenant_id, c.id, p.price_amount, p.price_currency, 'succeeded', 'simulated',
                   :key, app.current_user_id()
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
                 price_amount, price_currency, sold_by)
            SELECT p.tenant_id, :client_id, p.id, p.name, p.kind, p.credits, start.value,
                   start.value + p.validity_days - 1, p.price_amount, p.price_currency,
                   app.current_user_id()
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
    return load_entitlement(db, entitlement_id)


@router.post("/entitlements/{entitlement_id}/freezes", status_code=status.HTTP_201_CREATED)
def freeze_entitlement(entitlement_id: UUID, body: FreezeCreate, context: SalesDep) -> Entitlement:
    """Pauses the entitlement for the given days and extends its end date by as many days."""
    db = context.session
    current = load_entitlement(db, entitlement_id)
    if current.state in ("cancelled", "expired"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_active")
    if body.starts_on < current.starts_on or body.starts_on > current.ends_on:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="outside_validity")
    if any(f.starts_on <= body.ends_on and body.starts_on <= f.ends_on for f in current.freezes):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="overlapping_freeze")

    db.execute(
        text("""
            INSERT INTO app.entitlement_freezes
                (tenant_id, entitlement_id, starts_on, ends_on, reason, created_by)
            VALUES (:tenant_id, :id, :starts_on, :ends_on, :reason, app.current_user_id())
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id, "id": entitlement_id},
    )
    db.execute(
        text("""
            UPDATE app.entitlements SET ends_on = ends_on + :days, updated_at = now()
            WHERE id = :id
        """),
        {"days": (body.ends_on - body.starts_on).days + 1, "id": entitlement_id},
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
