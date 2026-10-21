"""The devices a person signs in from: a new one is emailed to them (go-live, GL1). Also the
person's two-step sign-in policy and the answers to their account status reminders (W2-1)."""

import datetime as dt
import hashlib
import logging
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep
from app.api.routes import ensure_profile
from app.core.audit import record_everywhere
from app.core.config import get_settings
from app.core.mfa import (
    RISK_VERSION,
    RiskSource,
    has_acknowledged_risk,
    record_risk_acknowledgement,
)
from app.messaging.email import Email, Sender, load_all_messages, sender_from_settings

router = APIRouter(prefix="/me/devices", tags=["account"])
policy_router = APIRouter(prefix="/me/security", tags=["account"])
reminders_router = APIRouter(prefix="/me/reminders", tags=["account"])
logger = logging.getLogger(__name__)

MAX_DEVICES = 20
# "Remind me in a week" about two-step sign-in.
MFA_SNOOZE = dt.timedelta(days=7)


def get_sender() -> Sender | None:
    return sender_from_settings()


SenderDep = Annotated[Sender | None, Depends(get_sender)]


class DeviceCheck(BaseModel):
    device_id: str = Field(min_length=16, max_length=128, description="Random, kept on the device")
    label: str = Field(default="", max_length=120, description="E.g. 'Chrome on Windows'")
    locale: str = Field(default="he", pattern="^(he|en)$")


class DeviceCheckResult(BaseModel):
    new_device: bool = Field(description="First time this device signs in to the account")


class LoginDevice(BaseModel):
    id: UUID
    label: str
    first_seen_at: datetime
    last_seen_at: datetime
    current: bool = Field(description="The device that asked")


class SecurityPolicy(BaseModel):
    mfa_enforced: bool = Field(description="Two-step sign-in is enforced on this server")
    mfa_required_from: dt.date | None = Field(
        description="Deprecated: always empty, two-step sign-in is optional for owners and managers"
    )
    mfa_required_now: bool = Field(
        description="Deprecated: always false, see mfa_risk_acknowledged"
    )
    mfa_risk_acknowledged: bool = Field(
        description="The person confirmed they understand the risk of working without a code "
        '(also their answer "I don\'t want two-step sign-in": no more reminders)'
    )
    mfa_reminder_snoozed_until: datetime | None = Field(
        default=None, description='"Remind me in a week": no reminder before this time'
    )


class RiskAcknowledgement(BaseModel):
    source: RiskSource = Field(
        default="settings",
        description="Where the person confirmed: security settings, the \"I don't want two-step "
        'sign-in" choice, or the window of a refused sensitive action',
    )


def device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def new_device_email(to: str, label: str, locale: str, now: datetime) -> Email:
    messages = load_all_messages(locale)["securityEmail"]
    when = now.astimezone(UTC).strftime("%d/%m/%Y %H:%M UTC")
    return Email(
        to=to,
        subject=messages["subject"],
        text=f"{messages['greeting']}\n\n{messages['body']}",
        locale=locale,
        details=(
            (messages["device"], label or messages["unknownDevice"]),
            (messages["when"], when),
        ),
        kind="security",
    )


def _send(sender: Sender, email: Email) -> None:
    try:
        sender.send(email)
    except Exception:  # an email that fails must never fail the sign-in
        logger.exception("new-device email failed")


@router.post("/check")
def check_device(
    body: DeviceCheck,
    user: UserDep,
    session: SessionDep,
    background: BackgroundTasks,
    sender: SenderDep,
) -> DeviceCheckResult:
    """Called once after each sign-in. A device the account has not signed in from before is
    emailed to the person, unless it is the first one ever (a new account)."""
    ensure_profile(session, user.id, user.email)
    hashed = device_hash(body.device_id)
    others = session.execute(
        text("SELECT count(*) FROM app.login_devices WHERE device_hash <> :hash"),
        {"hash": hashed},
    ).scalar_one()
    inserted = session.execute(
        text("""
            INSERT INTO app.login_devices (user_id, device_hash, label)
            VALUES (app.current_user_id(), :hash, :label)
            ON CONFLICT (user_id, device_hash)
            DO UPDATE SET last_seen_at = now(), label = EXCLUDED.label
            RETURNING (xmax = 0) AS inserted
        """),
        {"hash": hashed, "label": body.label},
    ).scalar_one()
    # Keep the list short: forget the devices unused for longest.
    session.execute(
        text("""
            DELETE FROM app.login_devices WHERE id IN (
                SELECT id FROM app.login_devices ORDER BY last_seen_at DESC OFFSET :keep
            )
        """),
        {"keep": MAX_DEVICES},
    )
    new = bool(inserted)
    if new and others:
        record_everywhere(session, "login.new_device", label=body.label)
    if new and others and sender is not None and user.email:
        background.add_task(
            _send, sender, new_device_email(user.email, body.label, body.locale, datetime.now(UTC))
        )
    return DeviceCheckResult(new_device=new)


class SecurityEventBody(BaseModel):
    kind: Literal["mfa_enabled", "mfa_disabled"]


@router.post("/events", status_code=204)
def security_event(body: SecurityEventBody, user: UserDep, session: SessionDep) -> None:
    """The web app reports that the person turned two-step sign-in on or off, so the businesses
    they work for can see it in their audit log."""
    ensure_profile(session, user.id, user.email)
    record_everywhere(session, body.kind.replace("_", ".", 1))


@policy_router.get("")
def security_policy(user: UserDep, session: SessionDep) -> SecurityPolicy:
    """What the apps tell people about two-step sign-in (the account status of owners and
    managers)."""
    snoozed = session.execute(
        text("SELECT mfa_reminder_snoozed_until FROM app.users WHERE id = app.current_user_id()")
    ).scalar_one_or_none()
    return SecurityPolicy(
        mfa_enforced=get_settings().mfa_on,
        mfa_required_from=None,
        mfa_required_now=False,
        mfa_risk_acknowledged=has_acknowledged_risk(session),
        mfa_reminder_snoozed_until=snoozed,
    )


@policy_router.post("/mfa-risk-acknowledgement", status_code=204)
def acknowledge_mfa_risk(
    user: UserDep,
    session: SessionDep,
    request: Request,
    body: RiskAcknowledgement | None = None,
) -> None:
    """The person read the warning about working without two-step sign-in and understands the
    risk. Kept with the time, address, browser, version of the text and screen, and shown in the
    audit log of their businesses. The apps then stop reminding them."""
    source = body.source if body else "settings"
    ensure_profile(session, user.id, user.email)
    record_risk_acknowledgement(session, request, user.id, source)
    record_everywhere(session, "mfa.risk_acknowledged", version=RISK_VERSION, source=source)


@reminders_router.post("/mfa/snooze", status_code=204)
def snooze_mfa_reminder(user: UserDep, session: SessionDep) -> None:
    """ "Remind me in a week": the account status leaves two-step sign-in out for seven days.
    Sensitive actions still ask for the code or the confirmed warning."""
    ensure_profile(session, user.id, user.email)
    session.execute(
        text("UPDATE app.users SET mfa_reminder_snoozed_until = :until WHERE id = :id"),
        {"until": datetime.now(UTC) + MFA_SNOOZE, "id": user.id},
    )


@reminders_router.post("/address/skip", status_code=204)
def skip_address_reminder(user: UserDep, session: SessionDep) -> None:
    """The home address is optional: "skip" stops the reminder. It can be filled in at any time
    in the account settings, and is asked for again only where it is needed (form 101)."""
    ensure_profile(session, user.id, user.email)
    session.execute(
        text("""
            UPDATE app.users
            SET address_reminder_skipped_at = coalesce(address_reminder_skipped_at, now())
            WHERE id = :id
        """),
        {"id": user.id},
    )


@router.get("")
def list_devices(
    session: SessionDep,
    device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> list[LoginDevice]:
    """The devices signed in from recently, newest first."""
    rows = session.execute(
        text("""
            SELECT id, label, first_seen_at, last_seen_at, device_hash
            FROM app.login_devices ORDER BY last_seen_at DESC LIMIT :limit
        """),
        {"limit": MAX_DEVICES},
    ).all()
    mine = device_hash(device_id) if device_id else None
    return [
        LoginDevice(
            id=row.id,
            label=row.label,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            current=row.device_hash == mine,
        )
        for row in rows
    ]
