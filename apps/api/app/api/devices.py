"""The devices a person signs in from: a new one is emailed to them (go-live, GL1)."""

import datetime as dt
import hashlib
import logging
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep
from app.api.routes import ensure_profile
from app.core.audit import record_everywhere
from app.core.config import get_settings
from app.messaging.email import Email, Sender, load_all_messages, sender_from_settings

router = APIRouter(prefix="/me/devices", tags=["account"])
policy_router = APIRouter(prefix="/me/security", tags=["account"])
logger = logging.getLogger(__name__)

MAX_DEVICES = 20


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
        description="From this day owners and managers need a code for sensitive actions"
    )
    mfa_required_now: bool = Field(description="Owners and managers need a code already")


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
def security_policy(user: UserDep) -> SecurityPolicy:
    """What the apps tell people about two-step sign-in (the banner for owners and managers)."""
    settings = get_settings()
    return SecurityPolicy(
        mfa_enforced=settings.mfa_on,
        mfa_required_from=settings.mfa_required_from,
        mfa_required_now=settings.mfa_required_from is None
        or dt.date.today() >= settings.mfa_required_from,
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
