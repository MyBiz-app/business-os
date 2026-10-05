"""The MyBiz console: businesses on the platform, their usage and billing, contact requests,
and MyBiz's own team (migration 0037). Each part needs a console permission; owners hold
them all. The database functions enforce the same rules."""

import datetime as dt
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import SessionDep

router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformPermission(StrEnum):
    BUSINESSES_READ = "businesses.read"
    BUSINESSES_ACT = "businesses.act"
    BILLING_MANAGE = "billing.manage"
    INBOX_MANAGE = "inbox.manage"
    USAGE_READ = "usage.read"
    STAFF_MANAGE = "staff.manage"


Level = Literal["primary_owner", "owner", "manager", "employee"]


def require_platform(permission: PlatformPermission | None = None) -> Callable[[Session], Session]:
    """Any active MyBiz team member, or one holding `permission`."""

    def check(session: SessionDep) -> Session:
        allowed = session.execute(
            text("SELECT app.platform_can(:p)")
            if permission
            else text("SELECT app.is_platform_admin()"),
            {"p": permission.value} if permission else {},
        ).scalar_one()
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return session

    return check


StaffDep = Annotated[Session, Depends(require_platform())]
AdminDep = Annotated[Session, Depends(require_platform(PlatformPermission.BUSINESSES_READ))]
UsageDep = Annotated[Session, Depends(require_platform(PlatformPermission.USAGE_READ))]
InboxDep = Annotated[Session, Depends(require_platform(PlatformPermission.INBOX_MANAGE))]
BillingDep = Annotated[Session, Depends(require_platform(PlatformPermission.BILLING_MANAGE))]
TeamDep = Annotated[Session, Depends(require_platform(PlatformPermission.STAFF_MANAGE))]


def run_rule(db: Session, sql: str, params: dict[str, Any]) -> None:
    """Calls a console function whose rules raise errors; maps them to HTTP errors."""
    try:
        with db.begin_nested():
            db.execute(text(sql), params)
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


class InboxUpdate(BaseModel):
    status: Literal["new", "in_progress", "done"] | None = None
    assignee: str | None = Field(default=None, description="'me', an email, or '' to clear")
    notes: str | None = Field(default=None, max_length=4000)


@router.get("/contact-requests")
def contact_requests(db: InboxDep) -> list[ContactRequest]:
    """The inbox: requests from the marketing site and complaints from businesses. Open ones
    first, then newest."""
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
def audit(db: StaffDep, limit: Annotated[int, Query(ge=1, le=500)] = 200) -> list[AuditEntry]:
    """What the MyBiz team did, newest first (owners only)."""
    try:
        with db.begin_nested():
            rows = (
                db.execute(text("SELECT * FROM app.platform_audit_list(:limit)"), {"limit": limit})
                .mappings()
                .all()
            )
    except DBAPIError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owners_only") from error
    return [AuditEntry.model_validate(dict(row)) for row in rows]
