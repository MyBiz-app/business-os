"""AI usage and who may use it (round 7, R8): the month's meter with its pace marker, the person's
own allowance, and the AI settings of one team member.

The business's numbers are for those who manage the AI team; everyone else sees only their own
allowance. Three limits can stop a question: the business's monthly pool, a person's monthly limit
and a person's daily pace (15% of the pool by default; the owner has none)."""

import calendar
import datetime as dt
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import budget
from app.api.deps import TenantContext, require
from app.api.staff import _ensure_member_in_reach
from app.commerce.modules import AI_DAILY_PACE_PERCENT, ai_extra_user_price
from app.core.audit import record
from app.core.permissions import Permission, effective_permissions

router = APIRouter(prefix="/ai", tags=["ai"])

UseDep = Annotated[TenantContext, Depends(require(Permission.AI_USE))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.AI_MANAGE))]

Level = Literal["ok", "warn", "over"]
WARN_AT = 80  # percent: the bar turns amber; red at 100


def _level(percent: float) -> Level:
    return "over" if percent >= 100 else "warn" if percent >= WARN_AT else "ok"


class BusinessMeter(BaseModel):
    used: float
    included: int
    limit: int | None = Field(description="Where questions stop; null: no limit")
    percent: float = Field(description="Used / included, in percent")
    level: Level
    reach_date: dt.date | None = Field(
        description="When the month's pool runs out at this pace; null if it will not"
    )
    questions_left: int | None = Field(description="About, at one credit per question")


class PersonMeter(BaseModel):
    used_month: float
    month_limit: int | None = Field(description="Their own monthly limit, if one is set")
    used_today: float
    day_limit: int | None = Field(description="Their daily pace; null: none (the owner)")
    questions_left_today: int | None = Field(description="About, at one credit per question")
    level: Level


class Meter(BaseModel):
    month_start: dt.date
    day_of_month: int
    days_in_month: int
    pace_percent: float = Field(description="How far into the month we are, in percent")
    business: BusinessMeter | None = Field(description="Only for those who manage the AI team")
    person: PersonMeter
    level: Level = Field(description="The worse of the two: what the small dot shows")


def _today(db: Session) -> dt.date:
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return dt.datetime.now(ZoneInfo(time_zone)).date()


def _person(db: Session, user_id: UUID, role: str, role_keys: frozenset[str], start: dt.date):
    month_limit = budget.person_limit(db, user_id, role_keys)
    used_month = budget.person_used(db, user_id, start)
    day_limit = budget.day_limit(db, user_id, role)
    used_today = budget.person_used_today(db, user_id)
    left = None if day_limit is None else max(int(day_limit - used_today), 0)
    if month_limit is not None:
        month_left = max(int(month_limit - used_month), 0)
        left = month_left if left is None else min(left, month_left)
    percents = [
        100 * used / limit
        for used, limit in ((used_month, month_limit), (used_today, day_limit))
        if limit
    ]
    return PersonMeter(
        used_month=round(used_month, 2),
        month_limit=month_limit,
        used_today=round(used_today, 2),
        day_limit=day_limit,
        questions_left_today=left,
        level=_level(max(percents, default=0)),
    )


def build_meter(context: TenantContext, user_id: UUID) -> Meter:
    from app.ai.agents import member_role_keys  # avoids an import cycle through ai_team

    db = context.session
    today = _today(db)
    start = today.replace(day=1)
    days = calendar.monthrange(today.year, today.month)[1]
    person = _person(db, user_id, context.role, member_role_keys(db, context.role), start)
    business = None
    level = person.level
    if Permission.AI_MANAGE in context.permissions:
        used = budget.credits_used(db, start)
        included = budget.credits_included(db)
        percent = 100 * used / included if included else 0
        reach = None
        if included and used > 0 and used < included:
            per_day = used / today.day
            reach = today + dt.timedelta(days=int((included - used) / per_day))
            if reach > start.replace(day=days):
                reach = None
        business = BusinessMeter(
            used=round(used, 2),
            included=included,
            limit=budget.credits_limit(db),
            percent=round(percent, 1),
            level=_level(percent),
            reach_date=reach,
            questions_left=max(int(included - used), 0),
        )
        level = max(level, business.level, key=("ok", "warn", "over").index)
    return Meter(
        month_start=start,
        day_of_month=today.day,
        days_in_month=days,
        pace_percent=round(100 * today.day / days, 1),
        business=business,
        person=person,
        level=level,
    )


@router.get("/meter")
def ai_meter(context: UseDep) -> Meter:
    """The month's AI meter: where the business is against its pool and against the calendar
    (managers), and the person's own allowance for today and the month."""
    user_id = context.session.execute(text("SELECT app.current_user_id()")).scalar_one()
    return build_meter(context, user_id)


class KindRow(BaseModel):
    key: Literal["asked", "scheduled"]
    credits: float


class UsageBreakdown(BaseModel):
    by_kind: list[KindRow]
    ai_users_allowed: int
    ai_users_count: int
    extra_ai_users: int
    extra_user_price_minor: int
    currency: str


@router.get("/usage/breakdown")
def ai_usage_breakdown(context: ManageDep) -> UsageBreakdown:
    """What the usage window adds to /ai/usage: questions people asked against tasks that ran by
    themselves, and how many people have AI access against what the module includes."""
    db = context.session
    start = _today(db).replace(day=1)
    rows = db.execute(
        text("""
            SELECT CASE WHEN EXISTS (SELECT 1 FROM app.ai_task_runs r
                                     WHERE 'ai_conversation:' || r.conversation_id = u.source_ref)
                        THEN 'scheduled' ELSE 'asked' END AS kind,
                   sum(u.quantity) AS credits
            FROM app.usage_events u JOIN app.tenants t ON t.id = u.tenant_id
            WHERE u.meter = 'ai_credits'
              AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone)
            GROUP BY 1
        """),
        {"start": start},
    )
    found = {r.kind: float(r.credits) for r in rows}
    currency = budget.spend_settings(db).currency
    return UsageBreakdown(
        by_kind=[KindRow(key=k, credits=round(found.get(k, 0), 2)) for k in ("asked", "scheduled")],
        ai_users_allowed=budget.ai_users_allowed(db),
        ai_users_count=budget.ai_users_count(db),
        extra_ai_users=budget.extra_ai_users(db),
        extra_user_price_minor=ai_extra_user_price(currency),
        currency=currency,
    )


class ExtraUsers(BaseModel):
    extra_ai_users: int = Field(ge=0, le=200)


@router.put("/extra-users")
def set_extra_ai_users(body: ExtraUsers, context: ManageDep) -> UsageBreakdown:
    """The paid "extra AI user" add-ons: each lets one more person use the AI team and adds 150
    credits to the month's pool. Cannot go below the people who already have access."""
    db = context.session
    if budget.ai_users_allowed(db) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="ai_module_required")
    included_users = budget.ai_users_allowed(db) - budget.extra_ai_users(db)
    if included_users + body.extra_ai_users < budget.ai_users_count(db):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="ai_users_in_use")
    db.execute(
        text("""
            INSERT INTO app.tenant_ai_settings (tenant_id, extra_ai_users)
            VALUES (app.current_tenant_id(), :n)
            ON CONFLICT (tenant_id) DO UPDATE SET extra_ai_users = :n, updated_at = now()
        """),
        {"n": body.extra_ai_users},
    )
    record(db, "ai.extra_users", extra_ai_users=body.extra_ai_users)
    return ai_usage_breakdown(context)


class MemberAi(BaseModel):
    user_id: UUID
    role_default: bool = Field(description="Whether their role gives AI access without a switch")
    ai_access: bool | None = Field(description="Their own switch; null: follow the role")
    has_access: bool
    monthly_credits: int | None = Field(description="Their own monthly limit; null: the business's")
    daily_percent: int | None = Field(description="Their own daily pace; null: the default")
    default_daily_percent: int = AI_DAILY_PACE_PERCENT
    day_limit: int | None
    used_month: float
    used_today: float
    ai_users_allowed: int
    ai_users_count: int
    is_owner: bool


def _member_ai(context: TenantContext, user_id: UUID) -> MemberAi:
    db = context.session
    role = _ensure_member_in_reach(context, user_id)
    row = db.execute(
        text("""
            SELECT m.ai_access, m.ai_daily_percent, r.permissions AS custom_permissions
            FROM app.tenant_members m LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
            WHERE m.user_id = :user
        """),
        {"user": user_id},
    ).one()
    base = effective_permissions(role, row.custom_permissions)
    limit = db.execute(
        text(
            "SELECT monthly_credits FROM app.ai_credit_limits "
            "WHERE subject_kind = 'user' AND subject_key = :key"
        ),
        {"key": str(user_id)},
    ).scalar()
    start = _today(db).replace(day=1)
    return MemberAi(
        user_id=user_id,
        role_default=Permission.AI_USE.value in base,
        ai_access=row.ai_access,
        has_access=Permission.AI_USE.value
        in effective_permissions(role, row.custom_permissions, row.ai_access),
        monthly_credits=limit,
        daily_percent=row.ai_daily_percent,
        day_limit=budget.day_limit(db, user_id, role),
        used_month=round(budget.person_used(db, user_id, start), 2),
        used_today=round(budget.person_used_today(db, user_id), 2),
        ai_users_allowed=budget.ai_users_allowed(db),
        ai_users_count=budget.ai_users_count(db),
        is_owner=role == "owner",
    )


@router.get("/members/{user_id}")
def get_member_ai(user_id: UUID, context: ManageDep) -> MemberAi:
    """One team member's AI settings and use, for the AI tab of the staff card."""
    return _member_ai(context, user_id)


class MemberAiUpdate(BaseModel):
    """Fields left out stay as they are; `null` clears a personal setting back to the default."""

    ai_access: bool | None = None
    monthly_credits: int | None = Field(default=None, ge=0, le=1_000_000)
    daily_percent: int | None = Field(default=None, ge=1, le=100)


@router.put("/members/{user_id}")
def update_member_ai(user_id: UUID, body: MemberAiUpdate, context: ManageDep) -> MemberAi:
    db = context.session
    current = _member_ai(context, user_id)
    sent = body.model_fields_set
    if current.is_owner and "ai_access" in sent:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="owner_always_has_ai")
    if "ai_access" in sent:
        before = current.has_access
        after = body.ai_access if body.ai_access is not None else current.role_default
        if after and not before and current.ai_users_count >= current.ai_users_allowed:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="ai_users_full")
        db.execute(
            text("UPDATE app.tenant_members SET ai_access = :v WHERE user_id = :user"),
            {"v": body.ai_access, "user": user_id},
        )
    if "daily_percent" in sent:
        db.execute(
            text("UPDATE app.tenant_members SET ai_daily_percent = :v WHERE user_id = :user"),
            {"v": body.daily_percent, "user": user_id},
        )
    if "monthly_credits" in sent:
        db.execute(
            text(
                "DELETE FROM app.ai_credit_limits "
                "WHERE subject_kind = 'user' AND subject_key = :key"
            ),
            {"key": str(user_id)},
        )
        if body.monthly_credits is not None:
            db.execute(
                text("""
                    INSERT INTO app.ai_credit_limits
                        (tenant_id, subject_kind, subject_key, monthly_credits)
                    VALUES (app.current_tenant_id(), 'user', :key, :credits)
                """),
                {"key": str(user_id), "credits": body.monthly_credits},
            )
    record(
        db,
        "ai.member_settings",
        entity_type="member",
        entity_id=user_id,
        fields=sorted(sent),
    )
    return _member_ai(context, user_id)
