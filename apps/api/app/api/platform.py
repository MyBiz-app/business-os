"""The MyBiz console: businesses on the platform, their usage and billing, contact requests,
and MyBiz's own team (migration 0037). Each part needs a console permission; owners hold
them all. The database functions enforce the same rules."""

import datetime as dt
import json
import logging
import os
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, UserDep
from app.api.modules import check_selection
from app.api.pagination import MAX_LIMIT, FullPageDep, Page, PageDep
from app.core import events, metrics
from app.core.config import get_settings
from app.core.mfa import require_aal2
from app.jobs import MAX_HOURS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformPermission(StrEnum):
    BUSINESSES_READ = "businesses.read"
    BUSINESSES_ACT = "businesses.act"
    BILLING_MANAGE = "billing.manage"
    INBOX_MANAGE = "inbox.manage"
    USAGE_READ = "usage.read"
    STAFF_MANAGE = "staff.manage"
    BROADCASTS_MANAGE = "broadcasts.manage"


Level = Literal["primary_owner", "owner", "manager", "employee"]


def require_platform(permission: PlatformPermission | None = None) -> Callable[[Session], Session]:
    """Any active MyBiz team member, or one holding `permission`."""

    def check(session: SessionDep, user: UserDep) -> Session:
        allowed = session.execute(
            text("SELECT app.platform_can(:p)")
            if permission
            else text("SELECT app.is_platform_admin()"),
            {"p": permission.value} if permission else {},
        ).scalar_one()
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        require_aal2(user.aal)
        return session

    return check


StaffDep = Annotated[Session, Depends(require_platform())]
AdminDep = Annotated[Session, Depends(require_platform(PlatformPermission.BUSINESSES_READ))]
UsageDep = Annotated[Session, Depends(require_platform(PlatformPermission.USAGE_READ))]
InboxDep = Annotated[Session, Depends(require_platform(PlatformPermission.INBOX_MANAGE))]
BillingDep = Annotated[Session, Depends(require_platform(PlatformPermission.BILLING_MANAGE))]
TeamDep = Annotated[Session, Depends(require_platform(PlatformPermission.STAFF_MANAGE))]


def run_rule(db: Session, sql: str, params: dict[str, Any]) -> Any:
    """Calls a console function whose rules raise errors; maps them to HTTP errors."""
    try:
        with db.begin_nested():
            return db.execute(text(sql), params).scalar()
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        detail = str(getattr(getattr(error.orig, "diag", None), "message_primary", "")) or "error"
        if code == "42501":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from error
        if code == "P0002":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from error
        if code in ("P0001", "23514"):
            raise HTTPException(status_code=422, detail=detail) from error
        raise


class PlatformBusiness(BaseModel):
    id: UUID
    name: str
    vertical: str
    locale: str
    currency: str
    time_zone: str
    created_at: dt.datetime
    members: int
    clients: int
    active_clients: int
    modules: list[str]
    ai_credits_30d: float
    bookings_30d: int
    owner_email: str | None


class UsagePoint(BaseModel):
    day: dt.date
    meter: str
    quantity: float


@router.get("/businesses")
def businesses(db: AdminDep, page: FullPageDep) -> list[PlatformBusiness]:
    rows = db.execute(
        text("SELECT * FROM app.platform_businesses() LIMIT :limit OFFSET :offset"),
        {"limit": page.limit, "offset": page.offset},
    ).mappings()
    return [PlatformBusiness.model_validate(dict(row)) for row in rows]


@router.get("/usage")
def usage(
    db: UsageDep,
    tenant_id: Annotated[UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[UsagePoint]:
    """Usage per day and meter, for one business or the whole platform."""
    rows = db.execute(
        text("SELECT * FROM app.platform_usage(:tenant_id, :days)"),
        {"tenant_id": tenant_id, "days": days},
    ).mappings()
    return [UsagePoint.model_validate(dict(row)) for row in rows]


class FunnelStep(BaseModel):
    key: str = Field(description="started, a wizard step, or completed")
    visitors: int


@router.get("/funnel")
def signup_funnel(db: UsageDep, days: Annotated[int, Query(ge=1, le=365)] = 30) -> list[FunnelStep]:
    """People who reached each step of the sign-up journey, in order, and how many finished."""
    counts = {
        (row.event, row.step): row.visitors
        for row in db.execute(text("SELECT * FROM app.platform_funnel(:days)"), {"days": days})
    }
    steps = [("started", counts.get(("signup_started", ""), 0))]
    steps += [(step, counts.get(("signup_step", step), 0)) for step in events.SIGNUP_STEPS]
    steps.append(("completed", counts.get(("signup_completed", ""), 0)))
    return [FunnelStep(key=key, visitors=visitors) for key, visitors in steps]


class ActivityDay(BaseModel):
    day: dt.date
    active_day: int = Field(description="Businesses with any activity that day")
    active_week: int = Field(description="Businesses with any activity in the 7 days up to it")


@router.get("/activity")
def activity(db: UsageDep, days: Annotated[int, Query(ge=1, le=90)] = 30) -> list[ActivityDay]:
    rows = db.execute(text("SELECT * FROM app.platform_activity(:days)"), {"days": days}).mappings()
    return [ActivityDay.model_validate(dict(row)) for row in rows]


class Consumer(BaseModel):
    tenant_id: UUID
    name: str
    messages: float
    ai_credits: float
    storage_bytes: int


@router.get("/top-consumers")
def top_consumers(
    db: UsageDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[Consumer]:
    """The businesses using the most messages, space and AI."""
    rows = db.execute(
        text("SELECT * FROM app.platform_top_consumers(:days, :limit)"),
        {"days": days, "limit": limit},
    ).mappings()
    return [Consumer.model_validate(dict(row)) for row in rows]


class AISpend(BaseModel):
    today: float = Field(description="AI credits (US cents) spent today across the platform, UTC")
    alert_at: int = Field(description="The daily alarm threshold, from API_AI_DAILY_ALERT_CREDITS")
    over: bool
    days: list[UsagePoint] = Field(description="AI credits per day, the last 7 days")


@router.get("/ai-spend")
def ai_spend(db: UsageDep) -> AISpend:
    """The daily AI spend alarm (P0-6): today's total against a configured threshold."""
    today = dt.datetime.now(dt.UTC).date()
    rows = db.execute(
        text("SELECT * FROM app.platform_usage(NULL, 7) WHERE meter = 'ai_credits'")
    ).mappings()
    days = [UsagePoint.model_validate(dict(row)) for row in rows]
    spent = sum(p.quantity for p in days if p.day == today)
    threshold = get_settings().ai_daily_alert_credits
    over = threshold > 0 and spent >= threshold
    if over:
        logger.warning("AI spend alarm: %.0f credits today, threshold %d", spent, threshold)
    return AISpend(today=spent, alert_at=threshold, over=over, days=days)


class JobHealth(BaseModel):
    job: str
    last_run_at: dt.datetime | None
    last_ok_at: dt.datetime | None
    last_ok: bool | None = Field(description="Did the latest finished run succeed")
    last_result: str | None
    runs_24h: int
    failures_24h: int
    late: bool = Field(description="Scheduled, and its last success is older than it allows")


class RouteTiming(BaseModel):
    route: str
    count: int
    p50_ms: float
    p95_ms: float


class RecentCrash(BaseModel):
    at: dt.datetime
    request_id: str | None
    method: str
    path: str | None
    tenant_id: UUID | None
    status: int
    error: str | None


class SystemHealth(BaseModel):
    jobs: list[JobHealth]
    messages_queued: int
    messages_failed_24h: int
    emails_waiting: int
    database_bytes: int
    ai_credits_today: float
    ai_alert_at: int
    routes: list[RouteTiming] = Field(description="Busiest routes of this API process")
    errors: list[RecentCrash] = Field(description="The last crashes of this API process")
    release: str | None = Field(description="The commit the API runs, when the host tells us")


@router.get("/health")
def system_health(db: UsageDep) -> SystemHealth:
    """What the console's "System health" page shows (go-live GL13). Job and queue numbers come
    from the database; timings and crashes are this API process's own (they reset on restart)."""
    data = db.execute(text("SELECT app.platform_health()")).scalar_one()
    now = dt.datetime.now(dt.UTC)
    late_after = {job: dt.timedelta(hours=hours) for job, hours in MAX_HOURS.items()}
    jobs = []
    for row in data["jobs"]:
        row["last_run_at"] = _timestamp(row["last_run_at"])
        row["last_ok_at"] = _timestamp(row["last_ok_at"])
        limit = late_after.get(row["job"])
        row["late"] = bool(limit and row["last_ok_at"] and now - row["last_ok_at"] > limit)
        jobs.append(JobHealth.model_validate(row))
    today = now.date()
    spent = sum(
        p.quantity
        for p in (
            UsagePoint.model_validate(dict(row))
            for row in db.execute(
                text("SELECT * FROM app.platform_usage(NULL, 2) WHERE meter = 'ai_credits'")
            ).mappings()
        )
        if p.day == today
    )
    return SystemHealth(
        jobs=jobs,
        messages_queued=data["messages_queued"],
        messages_failed_24h=data["messages_failed_24h"],
        emails_waiting=data["emails_waiting"],
        database_bytes=data["database_bytes"],
        ai_credits_today=spent,
        ai_alert_at=get_settings().ai_daily_alert_credits,
        routes=[RouteTiming(**vars(stat)) for stat in metrics.route_stats()],
        errors=[RecentCrash(**vars(error)) for error in metrics.recent_errors()],
        release=get_settings().sentry_release or os.environ.get("RENDER_GIT_COMMIT") or None,
    )


def _timestamp(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


class ContactRequest(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str | None
    business: str | None
    vertical: str | None
    message: str | None
    locale: str
    created_at: dt.datetime
    status: Literal["new", "in_progress", "done"]
    assignee: str | None
    notes: str | None
    tenant_id: UUID | None
    from_business: bool = Field(description="A complaint from inside a business, not the site")
    kind: Literal["request", "setup_guided", "setup_full"] = Field(
        default="request", description="setup_*: the business bought setup by the MyBiz team"
    )
    tier: Literal["standard", "priority", "vip"] = Field(
        default="standard", description="The business's support tier; open requests by tier"
    )


class InboxUpdate(BaseModel):
    status: Literal["new", "in_progress", "done"] | None = None
    assignee: str | None = Field(default=None, description="'me', an email, or '' to clear")
    notes: str | None = Field(default=None, max_length=4000)


@router.get("/contact-requests")
def contact_requests(db: InboxDep, page: FullPageDep) -> list[ContactRequest]:
    """The inbox: requests from the marketing site, complaints from businesses and setup tasks.
    Open ones first, VIP and priority support before standard, then newest."""
    rows = db.execute(
        text("SELECT * FROM app.platform_contact_requests() LIMIT :limit OFFSET :offset"),
        {"limit": page.limit, "offset": page.offset},
    ).mappings()
    return [ContactRequest.model_validate(dict(row)) for row in rows]


@router.patch("/contact-requests/{request_id}")
def update_contact_request(
    request_id: UUID, body: InboxUpdate, db: InboxDep
) -> list[ContactRequest]:
    """Moves a request along: status, who on the MyBiz side handles it, internal notes."""
    run_rule(
        db,
        "SELECT app.platform_inbox_update(:id, :status, :assignee, :notes)",
        {
            "id": request_id,
            "status": body.status,
            "assignee": body.assignee,
            "notes": body.notes,
        },
    )
    return contact_requests(db, Page(limit=MAX_LIMIT, offset=0))


class BillingMonth(BaseModel):
    month: dt.date
    currency: str
    invoices: int
    paid: int = Field(description="Minor units")
    open: int = Field(description="Minor units")


@router.get("/billing")
def billing_summary(db: BillingDep) -> list[BillingMonth]:
    """What MyBiz billed businesses, per month and currency (simulated charges)."""
    rows = db.execute(text("SELECT * FROM app.platform_billing_summary()")).mappings()
    return [BillingMonth.model_validate(dict(row)) for row in rows]


# --- MyBiz's team ---------------------------------------------------------------------------


class StaffMe(BaseModel):
    email: str
    level: Level
    permissions: list[PlatformPermission]


@router.get("/me")
def platform_me(db: StaffDep) -> StaffMe:
    """The signed-in team member's level and permissions (the console shows what they hold)."""
    row = db.execute(text("SELECT * FROM app.platform_me()")).mappings().one()
    return StaffMe.model_validate(dict(row))


class StaffMember(BaseModel):
    email: str
    level: Level
    permissions: list[PlatformPermission]
    disabled: bool
    full_name: str | None
    signed_up: bool = Field(description="Has signed in to MyBiz at least once")
    added_by: str | None
    created_at: dt.datetime


class StaffSave(BaseModel):
    level: Literal["owner", "manager", "employee"]
    permissions: list[PlatformPermission] = []
    disabled: bool = False


@router.get("/staff")
def list_staff(db: TeamDep) -> list[StaffMember]:
    rows = db.execute(text("SELECT * FROM app.platform_staff_list()")).mappings()
    return [StaffMember.model_validate(dict(row)) for row in rows]


@router.put("/staff/{email}")
def save_staff(email: EmailStr, body: StaffSave, db: TeamDep) -> list[StaffMember]:
    """Adds a team member or changes one. Nobody changes the primary owner or themselves;
    only owners handle owners and managers; nobody gives more than they hold."""
    run_rule(
        db,
        "SELECT app.platform_staff_save(:email, :level, CAST(:permissions AS text[]), :disabled)",
        {
            "email": email,
            "level": body.level,
            "permissions": sorted({p.value for p in body.permissions}),
            "disabled": body.disabled,
        },
    )
    return list_staff(db)


@router.delete("/staff/{email}")
def remove_staff(email: str, db: TeamDep) -> list[StaffMember]:
    run_rule(db, "SELECT app.platform_staff_remove(:email)", {"email": email})
    return list_staff(db)


class AuditEntry(BaseModel):
    occurred_at: dt.datetime
    actor_email: str
    action: str
    tenant_id: UUID | None
    tenant_name: str | None
    details: dict[str, Any]


@router.get("/audit")
def audit(db: StaffDep, page: PageDep) -> list[AuditEntry]:
    """What the MyBiz team did, newest first (owners only)."""
    try:
        with db.begin_nested():
            rows = (
                db.execute(
                    text("SELECT * FROM app.platform_audit_list(:limit)"),
                    {"limit": page.limit + page.offset},
                )
                .mappings()
                .all()[page.offset :]
            )
    except DBAPIError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owners_only") from error
    return [AuditEntry.model_validate(dict(row)) for row in rows]


# --- Actions on a business ------------------------------------------------------------------


class TrialExtension(BaseModel):
    days: int = Field(ge=1, le=180)


class Trial(BaseModel):
    trial_ends_at: dt.datetime


class ModulesChange(BaseModel):
    modules: dict[str, int] = Field(description="The business's new modules, like its own page")


class VoidInvoice(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class BusinessInvoice(BaseModel):
    id: UUID
    number: int
    period_start: dt.date
    period_end: dt.date
    currency: str
    total: int = Field(description="Minor units")
    status: Literal["open", "paid", "void"]
    issued_at: dt.datetime


@router.get("/businesses/{tenant_id}/invoices")
def business_invoices(tenant_id: UUID, db: BillingDep) -> list[BusinessInvoice]:
    """One business's invoices, newest first."""
    rows = db.execute(
        text("SELECT * FROM app.platform_business_invoices(:t)"), {"t": tenant_id}
    ).mappings()
    return [BusinessInvoice.model_validate(dict(row)) for row in rows]


@router.post("/businesses/{tenant_id}/trial")
def extend_trial(tenant_id: UUID, body: TrialExtension, db: BillingDep) -> Trial:
    """Gives a business more trial days (a goodwill gesture, a late start)."""
    until = run_rule(
        db, "SELECT app.platform_extend_trial(:t, :days)", {"t": tenant_id, "days": body.days}
    )
    return Trial(trial_ends_at=until)


@router.put("/businesses/{tenant_id}/modules")
def set_business_modules(tenant_id: UUID, body: ModulesChange, db: BillingDep) -> PlatformBusiness:
    """Changes a business's modules for it (a sale, a mistake to undo)."""
    check_selection(body.modules)
    run_rule(
        db,
        "SELECT app.platform_set_modules(:t, CAST(:modules AS jsonb))",
        {"t": tenant_id, "modules": json.dumps(body.modules)},
    )
    row = (
        db.execute(
            text("SELECT * FROM app.platform_businesses() WHERE id = :id"), {"id": tenant_id}
        )
        .mappings()
        .one()
    )
    return PlatformBusiness.model_validate(dict(row))


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: UUID, body: VoidInvoice, db: BillingDep) -> list[BillingMonth]:
    """Credits an invoice: it stops counting as due or paid, with the reason in both logs."""
    run_rule(
        db,
        "SELECT app.platform_void_invoice(:id, :reason)",
        {"id": invoice_id, "reason": body.reason},
    )
    return billing_summary(db)
