"""The welcome email for a new business (app/welcome.py): sent once, right after sign-up, to
the owner who signs up; the owner can also look at it again later."""

from typing import Annotated, Literal, get_args
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, require
from app.core.config import get_settings
from app.email import sender_from_settings
from app.payments import provider_for_business
from app.permissions import Permission
from app.welcome import WelcomeDetails, build_welcome

router = APIRouter(prefix="/tenants/current/welcome-email", tags=["tenants"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]


class WelcomeRequest(BaseModel):
    expected_active_clients: int = Field(
        default=0, ge=0, le=100_000, description="From the sign-up journey, for the core tier"
    )


class WelcomeEmail(BaseModel):
    status: Literal["sent", "logged", "not_configured", "already_sent", "preview"]
    to: str
    subject: str
    html: str = Field(description="The email as sent, to show it in the app")


def _details(db: Session, expected_active_clients: int) -> WelcomeDetails:
    row = (
        db.execute(
            text("""
                SELECT t.name, t.locale, t.currency, t.join_code, t.trial_ends_at, t.time_zone,
                       u.email
                FROM app.tenants t, app.users u
                WHERE t.id = app.current_tenant_id() AND u.id = app.current_user_id()
            """)
        )
        .mappings()
        .one()
    )
    modules = dict(
        db.execute(
            text("""
                SELECT module_key, quantity FROM app.tenant_modules
                WHERE tenant_id = app.current_tenant_id()
            """)
        ).all()
    )
    settings = get_settings()
    return WelcomeDetails(
        to=row["email"],
        business=row["name"],
        locale=row["locale"],
        currency=row["currency"],
        join_code=row["join_code"],
        trial_ends_on=row["trial_ends_at"].astimezone(ZoneInfo(row["time_zone"])).date(),
        modules=modules,
        expected_active_clients=expected_active_clients,
        web_url=settings.web_url.rstrip("/"),
        client_app_url=settings.client_app_url.rstrip("/"),
        simulated=provider_for_business() == "simulated",
    )


@router.post("")
def send_welcome(body: WelcomeRequest, context: SettingsDep) -> WelcomeEmail:
    """Sends the welcome email once; later calls return it without sending again."""
    db = context.session
    email = build_welcome(_details(db, body.expected_active_clients))
    claimed = db.execute(
        text("""
            UPDATE app.tenants SET welcome_sent_at = now()
            WHERE id = app.current_tenant_id() AND welcome_sent_at IS NULL RETURNING id
        """)
    ).scalar()
    if claimed is None:
        return WelcomeEmail(
            status="already_sent", to=email.to, subject=email.subject, html=email.html or ""
        )
    sender = sender_from_settings()
    if sender is None:
        status: Literal["sent", "logged", "not_configured"] = "not_configured"
    else:
        try:
            sender.send(email)
        except Exception as error:  # the business is created either way; tell the caller
            raise HTTPException(status_code=502, detail="email_failed") from error
        status = "logged" if get_settings().email_provider == "log" else "sent"
    return WelcomeEmail(status=status, to=email.to, subject=email.subject, html=email.html or "")


@router.get("")
def preview_welcome(context: SettingsDep) -> WelcomeEmail:
    email = build_welcome(_details(context.session, 0))
    return WelcomeEmail(status="preview", to=email.to, subject=email.subject, html=email.html or "")


# --- Getting started -----------------------------------------------------------------------

setup_router = APIRouter(prefix="/tenants/current/getting-started", tags=["tenants"])

SetupStep = Literal["branding", "services", "schedule", "team", "clients", "card"]


class SetupItem(BaseModel):
    key: SetupStep
    done: bool


class GettingStarted(BaseModel):
    steps: list[SetupItem]
    done: int
    total: int


@setup_router.get("")
def getting_started(context: SettingsDep) -> GettingStarted:
    """The first-steps checklist on the dashboard, from what the business has set up."""
    row = (
        context.session.execute(
            text("""
                SELECT
                    (t.logo IS NOT NULL OR t.primary_color IS NOT NULL) AS branding,
                    EXISTS (SELECT 1 FROM app.services x WHERE x.tenant_id = t.id) AS services,
                    (EXISTS (SELECT 1 FROM app.sessions x WHERE x.tenant_id = t.id)
                     OR EXISTS (SELECT 1 FROM app.staff_hours x WHERE x.tenant_id = t.id))
                        AS schedule,
                    ((SELECT count(*) FROM app.tenant_members m WHERE m.tenant_id = t.id) > 1
                     OR EXISTS (SELECT 1 FROM app.invitations x WHERE x.tenant_id = t.id)) AS team,
                    EXISTS (SELECT 1 FROM app.clients x WHERE x.tenant_id = t.id) AS clients,
                    EXISTS (SELECT 1 FROM app.billing_accounts b
                            WHERE b.tenant_id = t.id AND b.card_last4 IS NOT NULL) AS card
                FROM app.tenants t WHERE t.id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    steps = [SetupItem(key=key, done=bool(row[key])) for key in get_args(SetupStep)]
    return GettingStarted(steps=steps, done=sum(s.done for s in steps), total=len(steps))
