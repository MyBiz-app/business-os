"""Pay components, one-off bonuses and the dated rates (round 6, P3).

A team member's fixed monthly components (travel, meals, phone, car, a fixed addition,
recuperation, a fixed deduction) and the one-off additions and deductions of a month (bonus,
holiday gift, expense refund, deduction) are kept here; the pay run (P4) reads them.

`payroll.read` sees them (within one's reach and never above one's own level, owners see all),
`payroll.manage` changes them and adds bonuses straight away, and `payroll.propose` (a branch
manager) can only propose a bonus for people at their own branches, which the owner
(`payroll.approve`) then approves or rejects. Every change is written to the audit log."""

import json
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, TenantDep, UserDep, require
from app.api.staff import _ensure_member_in_reach
from app.core.permissions import Permission
from app.payroll.components import (
    ADJUSTMENT_FLAGS,
    COMPONENT_FLAGS,
    DEFAULT_CALC,
    AdjustmentKind,
    Calc,
    ComponentKind,
    split_evenly,
)

router = APIRouter(tags=["payroll"])

PayrollReadDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_READ))]
PayrollManageDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_MANAGE))]
PayrollApproveDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_APPROVE))]

# Nobody sees or sets the pay of someone at their own level or above, except the owner.
RANK = {"owner": 4, "manager": 3, "branch_manager": 2, "front_desk": 1, "staff": 1}


def _audit(
    session: Session, tenant_id: UUID, action: str, kind: str, entity_id: UUID, **details: Any
) -> None:
    session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (:tenant_id, 'user', app.current_user_id(), :action, :kind, :entity_id,
                    CAST(:details AS jsonb))
        """),
        {
            "tenant_id": tenant_id,
            "action": action,
            "kind": kind,
            "entity_id": entity_id,
            "details": json.dumps(details, default=str),
        },
    )


def _below(context: TenantContext, role: str) -> bool:
    return context.role == "owner" or RANK.get(role, 1) < RANK.get(context.role, 0)


def _ensure_below(context: TenantContext, user_id: UUID) -> None:
    """The member is in reach and below one's own level, else "not found"."""
    role = _ensure_member_in_reach(context, user_id)
    if not _below(context, role):
        raise not_found()


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _first_of_month(day: date) -> date:
    return day.replace(day=1)


def ensure_period_open(session: Session, period: date) -> None:
    """One-off amounts stop once the owner has approved the month's pay run (P4)."""
    locked = session.execute(
        text("SELECT 1 FROM app.payroll_runs WHERE period = :period AND stage = 'approved'"),
        {"period": _first_of_month(period)},
    ).first()
    if locked is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="period_locked")


# Pay components ------------------------------------------------------------------------------


class ComponentFields(BaseModel):
    kind: ComponentKind
    name: str = Field(min_length=1, max_length=120)
    calc: Calc | None = Field(
        default=None,
        description="per_work_day: amount x work days; monthly: fixed; by_month: typed in each"
        " month; automatic: from the rates table (recuperation by seniority)."
        " Default by kind.",
    )
    amount_minor: int | None = Field(default=None, ge=0)
    cap_minor: int | None = Field(default=None, ge=0, description="A ceiling on the monthly sum")
    currency: str = Field(default="ILS", pattern=r"^[A-Z]{3}$")
    taxable: bool | None = Field(default=None, description="Default by kind")
    social_security_liable: bool | None = Field(default=None, description="Default by kind")
    pension_base: bool | None = Field(default=None, description="Default by kind")
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def dates_in_order(self) -> "ComponentFields":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to before valid_from")
        return self


class ComponentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    calc: Calc | None = None
    amount_minor: int | None = Field(default=None, ge=0)
    cap_minor: int | None = Field(default=None, ge=0)
    taxable: bool | None = None
    social_security_liable: bool | None = None
    pension_base: bool | None = None
    valid_to: date | None = None


class PayComponent(BaseModel):
    id: UUID
    user_id: UUID
    kind: ComponentKind
    name: str
    calc: Calc
    amount_minor: int | None
    cap_minor: int | None
    currency: str
    taxable: bool
    social_security_liable: bool
    pension_base: bool
    valid_from: date
    valid_to: date | None


COMPONENT_COLUMNS = (
    "id, user_id, kind, name, calc, amount_minor, cap_minor, currency, taxable,"
    " social_security_liable, pension_base, valid_from, valid_to"
)


def _components(session: Session, user_id: UUID) -> list[PayComponent]:
    rows = session.execute(
        text(
            "SELECT " + COMPONENT_COLUMNS + " FROM app.pay_components WHERE user_id = :id"
            " ORDER BY valid_from, created_at"
        ),
        {"id": user_id},
    ).mappings()
    return [PayComponent.model_validate(dict(row)) for row in rows]


def _check_amount(calc: str, amount_minor: int | None) -> None:
    if calc not in ("by_month", "automatic") and amount_minor is None:
        raise _unprocessable("amount_required")


@router.get("/staff/{user_id}/pay-components")
def list_pay_components(user_id: UUID, context: PayrollReadDep) -> list[PayComponent]:
    _ensure_below(context, user_id)
    return _components(context.session, user_id)


@router.get("/me/pay-components")
def my_pay_components(context: TenantDep, user: UserDep) -> list[PayComponent]:
    """The signed-in team member's own components."""
    return _components(context.session, user.id)


@router.post("/staff/{user_id}/pay-components", status_code=status.HTTP_201_CREATED)
def add_pay_component(
    user_id: UUID, body: ComponentFields, context: PayrollManageDep
) -> PayComponent:
    _ensure_below(context, user_id)
    calc = body.calc or DEFAULT_CALC[body.kind]
    _check_amount(calc, body.amount_minor)
    flags = COMPONENT_FLAGS[body.kind]
    row = (
        context.session.execute(
            text(
                """
                INSERT INTO app.pay_components
                    (tenant_id, user_id, kind, name, calc, amount_minor, cap_minor, currency,
                     taxable, social_security_liable, pension_base, valid_from, valid_to)
                VALUES (:tenant_id, :user_id, :kind, :name, :calc, :amount, :cap, :currency,
                        :taxable, :ss, :pension, coalesce(:valid_from, current_date), :valid_to)
                RETURNING """
                + COMPONENT_COLUMNS
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": user_id,
                "kind": body.kind,
                "name": body.name,
                "calc": calc,
                "amount": body.amount_minor,
                "cap": body.cap_minor,
                "currency": body.currency,
                "taxable": flags.taxable if body.taxable is None else body.taxable,
                "ss": flags.social_security_liable
                if body.social_security_liable is None
                else body.social_security_liable,
                "pension": flags.pension_base if body.pension_base is None else body.pension_base,
                "valid_from": body.valid_from,
                "valid_to": body.valid_to,
            },
        )
        .mappings()
        .one()
    )
    created = PayComponent.model_validate(dict(row))
    _audit(
        context.session,
        context.tenant_id,
        "payroll.component_added",
        "member",
        user_id,
        component_id=created.id,
        component_kind=created.kind,
    )
    return created


def _component_owner(context: TenantContext, component_id: UUID) -> PayComponent:
    row = (
        context.session.execute(
            text("SELECT " + COMPONENT_COLUMNS + " FROM app.pay_components WHERE id = :id"),
            {"id": component_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    component = PayComponent.model_validate(dict(row))
    _ensure_below(context, component.user_id)
    return component


@router.patch("/pay-components/{component_id}")
def update_pay_component(
    component_id: UUID, body: ComponentUpdate, context: PayrollManageDep
) -> PayComponent:
    current = _component_owner(context, component_id)
    merged = {**current.model_dump(), **body.model_dump(exclude_unset=True)}
    if merged["valid_to"] is not None and merged["valid_to"] < merged["valid_from"]:
        raise _unprocessable("valid_to_before_valid_from")
    _check_amount(merged["calc"], merged["amount_minor"])
    row = (
        context.session.execute(
            text(
                """
                UPDATE app.pay_components
                SET name = :name, calc = :calc, amount_minor = :amount_minor,
                    cap_minor = :cap_minor, taxable = :taxable,
                    social_security_liable = :social_security_liable,
                    pension_base = :pension_base, valid_to = :valid_to, updated_at = now()
                WHERE id = :id
                RETURNING """
                + COMPONENT_COLUMNS
            ),
            {**merged, "id": component_id},
        )
        .mappings()
        .one()
    )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.component_changed",
        "member",
        current.user_id,
        component_id=component_id,
    )
    return PayComponent.model_validate(dict(row))


@router.delete("/pay-components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pay_component(component_id: UUID, context: PayrollManageDep) -> Response:
    current = _component_owner(context, component_id)
    context.session.execute(
        text("DELETE FROM app.pay_components WHERE id = :id"), {"id": component_id}
    )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.component_removed",
        "member",
        current.user_id,
        component_id=component_id,
        component_kind=current.kind,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Dated rates ---------------------------------------------------------------------------------


class PayrollRate(BaseModel):
    rate_key: str
    valid_from: date
    value: dict[str, Any]
    source: str
    verified: bool


@router.get("/payroll/rates")
def list_payroll_rates(
    context: PayrollReadDep, as_of: Annotated[date | None, Query()] = None
) -> list[PayrollRate]:
    """The rate in force on a date (today by default) for each rate key."""
    rows = context.session.execute(
        text("""
            SELECT DISTINCT ON (rate_key) rate_key, valid_from, value, source,
                   verified_at IS NOT NULL AS verified
            FROM app.payroll_rates
            WHERE valid_from <= coalesce(:as_of, current_date)
            ORDER BY rate_key, valid_from DESC
        """),
        {"as_of": as_of},
    ).mappings()
    return [PayrollRate.model_validate(dict(row)) for row in rows]


# Bonuses and one-off adjustments --------------------------------------------------------------

TargetKind = Literal[
    "employee", "location", "location_group", "managers", "role", "everyone", "manual"
]
# Each group's filter on `tenant_members m`, with only bound parameters.
TARGET_FILTER = {
    "employee": "m.user_id = ANY(CAST(:user_ids AS uuid[]))",
    "manual": "m.user_id = ANY(CAST(:user_ids AS uuid[]))",
    "location": "CAST(:location_id AS uuid) = ANY(m.location_ids)",
    "location_group": """m.location_ids && ARRAY(
        SELECT location_id FROM app.location_group_members
        WHERE group_id = CAST(:group_id AS uuid))""",
    "managers": "m.role IN ('manager', 'branch_manager')",
    "role": "m.role = :role",
    "everyone": "true",
}
MAX_RECIPIENTS = 500


class Target(BaseModel):
    kind: TargetKind
    user_ids: list[UUID] = Field(default_factory=list, max_length=MAX_RECIPIENTS)
    location_id: UUID | None = None
    group_id: UUID | None = None
    role: Literal["owner", "manager", "branch_manager", "front_desk", "staff"] | None = None

    @model_validator(mode="after")
    def complete(self) -> "Target":
        missing = {
            "employee": len(self.user_ids) != 1,
            "manual": not self.user_ids,
            "location": self.location_id is None,
            "location_group": self.group_id is None,
            "role": self.role is None,
        }.get(self.kind, False)
        if missing:
            raise ValueError("target_incomplete")
        return self


class BonusBody(BaseModel):
    target: Target
    kind: AdjustmentKind = "bonus"
    period: date = Field(description="Any day of the pay month")
    amount_mode: Literal["each", "split_total"] = Field(
        default="each", description="each: this amount for everyone; split_total: divide it"
    )
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="ILS", pattern=r"^[A-Z]{3}$")
    note: str | None = Field(default=None, max_length=200, description="Shown on the payslip")
    taxable: bool | None = Field(default=None, description="Default by kind")
    social_security_liable: bool | None = Field(default=None, description="Default by kind")
    pension_base: bool | None = Field(default=None, description="Default by kind")

    @field_validator("note", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value


class Recipient(BaseModel):
    user_id: UUID
    full_name: str | None
    email: str
    role: str
    amount_minor: int


class BonusPreview(BaseModel):
    recipients: list[Recipient]
    total_minor: int
    currency: str
    without_payroll_file: int = Field(
        description="People in the group with no employment terms yet: they get nothing"
    )
    out_of_reach: int = Field(description="People left out: other branches, or at your level")


class BonusBatch(BaseModel):
    batch_id: UUID
    status: Literal["proposed", "approved"]
    count: int
    total_minor: int
    currency: str
    kind: AdjustmentKind
    period: date


class Adjustment(BaseModel):
    id: UUID
    batch_id: UUID
    user_id: UUID
    full_name: str | None
    kind: AdjustmentKind
    period: date
    amount_minor: int
    currency: str
    note: str | None
    taxable: bool
    social_security_liable: bool
    pension_base: bool
    status: Literal["proposed", "approved", "rejected"]
    proposed_by: UUID | None
    created_at: str


class Decision(BaseModel):
    approve: bool


def _may_add(context: TenantContext) -> bool:
    return (
        Permission.PAYROLL_MANAGE in context.permissions
        or Permission.PAYROLL_PROPOSE in context.permissions
    )


def _resolve(context: TenantContext, body: BonusBody) -> BonusPreview:
    if not _may_add(context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    target = body.target
    rows = context.session.execute(
        text(
            """
            SELECT m.user_id, u.full_name, u.email, m.role, m.location_ids,
                   p.id IS NOT NULL AS has_file
            FROM app.tenant_members m
            JOIN app.users u ON u.id = m.user_id
            LEFT JOIN app.employment_profiles p
                   ON p.tenant_id = m.tenant_id AND p.user_id = m.user_id
            WHERE m.tenant_id = app.current_tenant_id() AND """
            + TARGET_FILTER[target.kind]
            + " ORDER BY coalesce(u.full_name, u.email), m.user_id"
        ),
        {
            "user_ids": [str(user_id) for user_id in target.user_ids],
            "location_id": str(target.location_id) if target.location_id else None,
            "group_id": str(target.group_id) if target.group_id else None,
            "role": target.role,
        },
    ).mappings()
    kept, out_of_reach, without_file = [], 0, 0
    for row in rows:
        reachable = _below(context, row["role"]) and (
            context.branches is None
            or (row["location_ids"] and set(row["location_ids"]) <= context.branches)
        )
        if not reachable:
            out_of_reach += 1
        elif not row["has_file"]:
            without_file += 1
        else:
            kept.append(row)
    if not kept:
        raise _unprocessable("no_recipients")
    if body.amount_mode == "split_total":
        if body.amount_minor < len(kept):
            raise _unprocessable("amount_too_small")
        shares = split_evenly(body.amount_minor, len(kept))
    else:
        shares = [body.amount_minor] * len(kept)
    recipients = [
        Recipient(
            user_id=row["user_id"],
            full_name=row["full_name"],
            email=row["email"],
            role=row["role"],
            amount_minor=share,
        )
        for row, share in zip(kept, shares, strict=True)
    ]
    return BonusPreview(
        recipients=recipients,
        total_minor=sum(shares),
        currency=body.currency,
        without_payroll_file=without_file,
        out_of_reach=out_of_reach,
    )


@router.post("/payroll/bonuses/preview")
def preview_bonus(body: BonusBody, context: TenantDep) -> BonusPreview:
    """Who would get what, without saving anything."""
    return _resolve(context, body)


@router.post("/payroll/bonuses", status_code=status.HTTP_201_CREATED)
def add_bonus(body: BonusBody, context: TenantDep, user: UserDep) -> BonusBatch:
    """Adds a one-off amount to every person of a group. With `payroll.manage` it is approved
    straight away; a branch manager (`payroll.propose`) only proposes, for the owner to decide."""
    preview = _resolve(context, body)
    ensure_period_open(context.session, body.period)
    approved = Permission.PAYROLL_MANAGE in context.permissions
    flags = ADJUSTMENT_FLAGS[body.kind]
    batch_id = uuid4()
    for recipient in preview.recipients:
        context.session.execute(
            text("""
                INSERT INTO app.pay_adjustments
                    (tenant_id, user_id, period, kind, amount_minor, currency, note, taxable,
                     social_security_liable, pension_base, status, batch_id, proposed_by,
                     created_by, decided_by, decided_at)
                VALUES (:tenant_id, :user_id, :period, :kind, :amount, :currency, :note,
                        :taxable, :ss, :pension, :status, :batch_id, :proposed_by, :actor,
                        CASE WHEN :status = 'approved' THEN :actor END,
                        CASE WHEN :status = 'approved' THEN now() END)
            """),
            {
                "tenant_id": context.tenant_id,
                "user_id": recipient.user_id,
                "period": _first_of_month(body.period),
                "kind": body.kind,
                "amount": recipient.amount_minor,
                "currency": body.currency,
                "note": body.note,
                "taxable": flags.taxable if body.taxable is None else body.taxable,
                "ss": flags.social_security_liable
                if body.social_security_liable is None
                else body.social_security_liable,
                "pension": flags.pension_base if body.pension_base is None else body.pension_base,
                "status": "approved" if approved else "proposed",
                "batch_id": batch_id,
                "proposed_by": None if approved else user.id,
                "actor": user.id,
            },
        )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.bonus_added" if approved else "payroll.bonus_proposed",
        "pay_batch",
        batch_id,
        count=len(preview.recipients),
        total_minor=preview.total_minor,
        bonus_kind=body.kind,
        period=_first_of_month(body.period),
    )
    return BonusBatch(
        batch_id=batch_id,
        status="approved" if approved else "proposed",
        count=len(preview.recipients),
        total_minor=preview.total_minor,
        currency=body.currency,
        kind=body.kind,
        period=_first_of_month(body.period),
    )


@router.get("/payroll/bonuses")
def list_bonuses(
    context: TenantDep,
    user: UserDep,
    period: Annotated[date | None, Query(description="Any day of the pay month")] = None,
    user_id: UUID | None = None,
    adjustment_status: Annotated[
        Literal["proposed", "approved", "rejected"] | None, Query(alias="status")
    ] = None,
) -> list[Adjustment]:
    """Payroll readers see the amounts within their reach and below their level; someone who can
    only propose sees just their own proposals."""
    can_read = Permission.PAYROLL_READ in context.permissions
    if not can_read and Permission.PAYROLL_PROPOSE not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    rows = context.session.execute(
        text("""
            SELECT a.id, a.batch_id, a.user_id, u.full_name, a.kind, a.period, a.amount_minor,
                   a.currency, a.note, a.taxable, a.social_security_liable, a.pension_base,
                   a.status, a.proposed_by, a.created_at::text AS created_at,
                   m.role, m.location_ids
            FROM app.pay_adjustments a
            JOIN app.users u ON u.id = a.user_id
            JOIN app.tenant_members m ON m.tenant_id = a.tenant_id AND m.user_id = a.user_id
            WHERE (CAST(:period AS date) IS NULL OR a.period = CAST(:period AS date))
              AND (CAST(:user_id AS uuid) IS NULL OR a.user_id = CAST(:user_id AS uuid))
              AND (CAST(:status AS text) IS NULL OR a.status = CAST(:status AS text))
              AND (CAST(:own_only AS boolean) IS FALSE OR a.proposed_by = :me)
            ORDER BY a.period DESC, a.created_at DESC, a.id
            LIMIT 500
        """),
        {
            "period": _first_of_month(period) if period else None,
            "user_id": user_id,
            "status": adjustment_status,
            "own_only": not can_read,
            "me": user.id,
        },
    ).mappings()
    return [
        Adjustment.model_validate(dict(row))
        for row in rows
        if _below(context, row["role"])
        and (
            context.branches is None
            or (row["location_ids"] and set(row["location_ids"]) <= context.branches)
        )
    ]


@router.post("/payroll/bonuses/{batch_id}/decision")
def decide_bonus(batch_id: UUID, body: Decision, context: PayrollApproveDep, user: UserDep) -> dict:
    """The owner approves or rejects a branch manager's proposal (all of its people at once)."""
    period = context.session.execute(
        text("SELECT period FROM app.pay_adjustments WHERE batch_id = :batch_id LIMIT 1"),
        {"batch_id": batch_id},
    ).scalar()
    if period is not None:
        ensure_period_open(context.session, period)
    changed = context.session.execute(
        text("""
            UPDATE app.pay_adjustments
            SET status = CASE WHEN :approve THEN 'approved' ELSE 'rejected' END,
                decided_by = :me, decided_at = now()
            WHERE batch_id = :batch_id AND status = 'proposed'
        """),
        {"approve": body.approve, "me": user.id, "batch_id": batch_id},
    ).rowcount
    if not changed:
        raise not_found()
    _audit(
        context.session,
        context.tenant_id,
        "payroll.bonus_approved" if body.approve else "payroll.bonus_rejected",
        "pay_batch",
        batch_id,
        count=changed,
    )
    return {"batch_id": str(batch_id), "status": "approved" if body.approve else "rejected"}


@router.delete("/payroll/adjustments/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adjustment(adjustment_id: UUID, context: TenantDep, user: UserDep) -> Response:
    """Removes one person's line. A payroll manager can remove any line below their level; a
    proposer only their own proposal that is still waiting."""
    row = (
        context.session.execute(
            text("""
                SELECT a.user_id, a.status, a.proposed_by, a.batch_id, a.period
                FROM app.pay_adjustments a WHERE a.id = :id
            """),
            {"id": adjustment_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    ensure_period_open(context.session, row["period"])
    if Permission.PAYROLL_MANAGE in context.permissions:
        _ensure_below(context, row["user_id"])
    elif not (row["status"] == "proposed" and row["proposed_by"] == user.id):
        raise not_found()
    context.session.execute(
        text("DELETE FROM app.pay_adjustments WHERE id = :id"), {"id": adjustment_id}
    )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.adjustment_removed",
        "member",
        row["user_id"],
        batch_id=row["batch_id"],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
