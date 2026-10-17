"""The MyBiz console: businesses on the platform, their usage and billing, contact requests,
and MyBiz's own team (migration 0037). Each part needs a console permission; owners hold
them all. The database functions enforce the same rules."""

import datetime as dt
import json
import logging
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
from app.api.pagination import PageDep
from app.core.config import get_settings
from app.core.mfa import require_aal2

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
def businesses(db: AdminDep) -> list[PlatformBusiness]:
    rows = db.execute(text("SELECT * FROM app.platform_businesses()")).mappings()
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
def contact_requests(db: InboxDep) -> list[ContactRequest]:
    """The inbox: requests from the marketing site, complaints from businesses and setup tasks.
    Open ones first, VIP and priority support before standard, then newest."""
    rows = db.execute(text("SELECT * FROM app.platform_contact_requests()")).mappings()
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
    return contact_requests(db)


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
    return next(b for b in businesses(db) if b.id == tenant_id)


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: UUID, body: VoidInvoice, db: BillingDep) -> list[BillingMonth]:
    """Credits an invoice: it stops counting as due or paid, with the reason in both logs."""
    run_rule(
        db,
        "SELECT app.platform_void_invoice(:id, :reason)",
        {"id": invoice_id, "reason": body.reason},
    )
    return billing_summary(db)


# --- Collecting unpaid invoices (GL20) --------------------------------------------------------


class OverdueBusiness(BaseModel):
    tenant_id: UUID
    name: str
    owner_email: str | None
    currency: str
    open_invoices: int
    open_amount: int = Field(description="Minor units, VAT included")
    oldest_issued_at: dt.datetime
    billing_state: Literal["active", "read_only", "suspended"]
    grace_until: dt.datetime | None


@router.get("/billing/overdue")
def overdue_businesses(db: BillingDep) -> list[OverdueBusiness]:
    """Businesses with an unpaid invoice, the oldest first."""
    rows = db.execute(text("SELECT * FROM app.platform_overdue_businesses()")).mappings()
    return [OverdueBusiness.model_validate(dict(row)) for row in rows]


class GraceExtension(BaseModel):
    days: int = Field(ge=1, le=90)


@router.post("/businesses/{tenant_id}/billing/grace")
def extend_grace(tenant_id: UUID, body: GraceExtension, db: BillingDep) -> list[OverdueBusiness]:
    """Gives a business more time to pay: lifts read-only or suspension now and holds off the
    next one for `days` days (reminders still go out)."""
    run_rule(
        db,
        "SELECT app.platform_extend_grace(:t, :days)",
        {"t": tenant_id, "days": body.days},
    )
    return overdue_businesses(db)


class DunningSettings(BaseModel):
    enabled: bool = Field(description="Off: no reminders, no read-only, no suspension")
    reminder_days: list[Annotated[int, Field(ge=0, le=60)]] = Field(
        max_length=6, description="Days after the invoice is issued that a reminder goes out"
    )
    read_only_after_days: int = Field(ge=1, le=120)
    suspend_after_days: int = Field(ge=2, le=180)


@router.get("/billing/dunning")
def get_dunning(db: BillingDep) -> DunningSettings:
    row = db.execute(text("SELECT * FROM app.dunning_settings")).mappings().one()
    return DunningSettings.model_validate(dict(row))


@router.put("/billing/dunning")
def set_dunning(body: DunningSettings, db: BillingDep) -> DunningSettings:
    if body.suspend_after_days <= body.read_only_after_days:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bad_order")
    run_rule(
        db,
        "SELECT app.platform_dunning_update("
        ":enabled, CAST(:days AS integer[]), :read_only, :suspend)",
        {
            "enabled": body.enabled,
            "days": sorted(set(body.reminder_days)),
            "read_only": body.read_only_after_days,
            "suspend": body.suspend_after_days,
        },
    )
    return get_dunning(db)
