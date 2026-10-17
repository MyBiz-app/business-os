"""After a move: tell the clients, and ask the MyBiz team to do the move for the business
(round 6, M3).

The notice goes to the clients a move created, through the free channels only (email; push and
pop-up reach those who already have an account). Clients who have only a phone number come back as
ready-to-open WhatsApp links the owner sends from their own phone: the paid WhatsApp and SMS
providers stay disabled adapters. Nothing here is stored in a new table: what was sent and what was
asked of MyBiz is read back from the audit log.

"Do it for me" opens a task in the console's inbox (the existing complaint path, marked
`[migration]`), and lets MyBiz support in for a limited time, which the business can end early."""

import json
import re
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.common import not_found
from app.api.deps import TenantContext, has_module, require
from app.api.messaging import (
    CampaignCreate,
    PlaceholderWarning,
    Recipient,
    _announce,
    _business,
    _by_channel,
    _values,
    render,
)
from app.catalog.importing import phone_key
from app.core.permissions import Permission
from app.messaging.placeholders import missing_counts

router = APIRouter(prefix="/migration", tags=["migration"])

ManageDep = Annotated[TenantContext, Depends(require(Permission.MIGRATION_MANAGE))]

NoticeChannel = Literal["email", "push", "popup"]
MAX_LINKS = 300  # WhatsApp links returned for the owner to open one by one
MARKER = "[migration]"


def _bad_request(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=code)


class NoticeRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=1000)
    channels: list[NoticeChannel] = Field(min_length=1, max_length=3)
    dry_run: bool = Field(default=True, description="Only count and preview; send nothing")
    resend: bool = Field(default=False, description="Send again after a notice already went out")

    @field_validator("subject", "body")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class PhoneOnlyClient(BaseModel):
    client_id: UUID
    first_name: str
    phone: str
    text: str = Field(description="The notice as this client gets it")
    whatsapp_link: str | None = Field(
        description="Opens WhatsApp with the text; null if no usable number"
    )


class NoticeOut(BaseModel):
    recipients: int = Field(
        description="Clients of the move that can be reached on a chosen channel"
    )
    clients: int = Field(description="Everyone the move created")
    by_channel: dict[str, int]
    preview: str | None
    warnings: list[PlaceholderWarning]
    sent: bool
    phone_only: list[PhoneOnlyClient] = Field(
        description="Clients with a phone number and no email: the owner sends these from WhatsApp"
    )
    phone_only_total: int


class FollowUpOut(BaseModel):
    clients: int = Field(description="Clients the move created")
    with_email: int
    with_phone_only: int
    notice_sent_at: datetime | None
    notice_recipients: int | None
    concierge_requested_at: datetime | None
    concierge_included: bool = Field(description="The business bought the done-for-you setup")
    support_until: datetime | None = Field(description="MyBiz support may look in until then")


class ConciergeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    support_hours: int = Field(default=72, ge=1, le=72, description="How long MyBiz may look in")


class ConciergeOut(BaseModel):
    requested_at: datetime
    included: bool
    support_until: datetime


def _session(context: TenantContext, session_id: UUID) -> tuple[str, int]:
    row = context.session.execute(
        text("""
            SELECT s.origin, (SELECT count(*) FROM app.import_files f WHERE f.session_id = s.id)
            FROM app.import_sessions s WHERE s.id = :id AND s.status <> 'cancelled'
        """),
        {"id": session_id},
    ).first()
    if row is None:
        raise not_found()
    return row[0], row[1]


def _moved_clients(context: TenantContext, session_id: UUID) -> list[Recipient]:
    """The clients the move created and still stands (an undone batch has none)."""
    rows = context.session.execute(
        text("""
            SELECT c.id AS client_id, c.user_id, c.first_name, c.phone, lower(c.email) AS email
            FROM app.import_batch_items i
            JOIN app.import_batches b ON b.id = i.batch_id AND b.tenant_id = i.tenant_id
            JOIN app.clients c ON c.id = i.entity_id AND c.tenant_id = i.tenant_id
            WHERE b.session_id = :s AND b.status = 'done' AND i.entity = 'client'
              AND c.erased_at IS NULL
            ORDER BY c.first_name, c.id
        """),
        {"s": session_id},
    ).mappings()
    return [Recipient.model_validate(dict(r)) for r in rows]


def _has(value: str | None) -> bool:
    return bool(value and value.strip())


def _whatsapp_link(phone: str, message: str) -> str | None:
    digits = phone_key(phone)
    if digits.startswith("0"):  # a national number: Israel, where the platform starts
        digits = "972" + digits[1:]
    if not re.fullmatch(r"\d{8,15}", digits):
        return None
    return f"https://wa.me/{digits}?text={quote(message)}"


def _audit(context: TenantContext, action: str, details: dict[str, object]) -> None:
    context.session.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (:t, 'user', app.current_user_id(), :action, CAST(:details AS jsonb))
        """),
        {"t": context.tenant_id, "action": action, "details": json.dumps(details)},
    )


def _last(context: TenantContext, action: str, session_id: UUID) -> tuple[datetime, dict] | None:
    row = context.session.execute(
        text("""
            SELECT occurred_at, details FROM app.audit_log
            WHERE action = :action AND details ->> 'session' = :s
            ORDER BY occurred_at DESC LIMIT 1
        """),
        {"action": action, "s": str(session_id)},
    ).first()
    return (row[0], row[1]) if row else None


def _support_until(context: TenantContext) -> datetime | None:
    return context.session.execute(
        text("""
            SELECT max(expires_at) FROM app.support_grants
            WHERE revoked_at IS NULL AND expires_at > now()
        """)
    ).scalar_one()


@router.get("/sessions/{session_id}/follow-up")
def follow_up(session_id: UUID, context: ManageDep) -> FollowUpOut:
    """Where a move stands after the import: who can be told, what went out, what MyBiz got."""
    _session(context, session_id)
    people = _moved_clients(context, session_id)
    notice = _last(context, "migration.notice", session_id)
    concierge = _last(context, "migration.concierge", session_id)
    return FollowUpOut(
        clients=len(people),
        with_email=sum(1 for p in people if _has(p.email)),
        with_phone_only=sum(1 for p in people if not _has(p.email) and _has(p.phone)),
        notice_sent_at=notice[0] if notice else None,
        notice_recipients=notice[1].get("recipients") if notice else None,
        concierge_requested_at=concierge[0] if concierge else None,
        concierge_included=has_module(context.session, "setup_full"),
        support_until=_support_until(context),
    )


@router.post("/sessions/{session_id}/notice")
def send_notice(session_id: UUID, body: NoticeRequest, context: ManageDep) -> NoticeOut:
    """Tells the clients of the move that the business has moved (a service message, so it needs
    no marketing consent). The text may use the variables of the messages editor; `{join_code}`
    and `{app_link}` take the client to the app."""
    db = context.session
    _session(context, session_id)
    people = _moved_clients(context, session_id)
    if not people:
        raise _bad_request("no_clients")
    business = _business(db)
    values = _values(db, context.tenant_id, people, business)
    reachable = [
        (p, v)
        for p, v in zip(people, values, strict=True)
        if (_has(p.email) and "email" in body.channels)
        or (p.user_id is not None and ("popup" in body.channels or "push" in body.channels))
    ]
    reach_people = [p for p, _ in reachable]
    reach_values = [v for _, v in reachable]
    phone_only = [
        (p, v)
        for p, v in zip(people, values, strict=True)
        if not _has(p.email) and _has(p.phone) and p.user_id is None
    ]
    links = []
    for p, v in phone_only[:MAX_LINKS]:
        message = render(body.body, v)
        links.append(
            PhoneOnlyClient(
                client_id=p.client_id,  # type: ignore[arg-type]
                first_name=p.first_name,
                phone=(p.phone or "").strip(),
                text=message,
                whatsapp_link=_whatsapp_link(p.phone or "", message),
            )
        )
    warnings = [
        PlaceholderWarning(variable=name, recipients=n)
        for name, n in missing_counts(body.body, reach_values or values).items()
    ]
    result = NoticeOut(
        recipients=len(reach_people),
        clients=len(people),
        by_channel=_by_channel(db, reach_people, list(body.channels)),
        preview=render(body.body, (reach_values or values)[0]),
        warnings=warnings,
        sent=False,
        phone_only=links,
        phone_only_total=len(phone_only),
    )
    if body.dry_run:
        return result
    if not reach_people:
        raise _bad_request("nobody_reachable")
    if _last(context, "migration.notice", session_id) and not body.resend:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_sent")
    announcement = CampaignCreate(
        audience="active",
        channels=list(body.channels),
        subject=body.subject,
        body=body.body,
        promotional=False,
    )
    _announce(context, reach_people, list(body.channels), announcement, None, business)
    _audit(
        context,
        "migration.notice",
        {
            "session": str(session_id),
            "recipients": len(reach_people),
            "channels": list(body.channels),
        },
    )
    result.sent = True
    return result


@router.post("/sessions/{session_id}/concierge", status_code=status.HTTP_201_CREATED)
def ask_concierge(session_id: UUID, body: ConciergeRequest, context: ManageDep) -> ConciergeOut:
    """ "Do it for me": opens a task in the MyBiz console's inbox for this move and lets MyBiz
    support look in for a limited time (ended early from the support settings). The business keeps
    the last word: it still approves the dry run itself."""
    db = context.session
    origin, files = _session(context, session_id)
    if files == 0:
        raise _bad_request("no_files")
    if _last(context, "migration.concierge", session_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_requested")
    included = has_module(db, "setup_full")
    db.execute(
        text("""
            UPDATE app.support_grants SET revoked_at = now(), revoked_by = app.current_user_id()
            WHERE revoked_at IS NULL AND expires_at > now()
        """)
    )
    expires = db.execute(
        text("""
            INSERT INTO app.support_grants (tenant_id, granted_by, expires_at)
            VALUES (:t, app.current_user_id(), now() + make_interval(hours => :hours))
            RETURNING expires_at
        """),
        {"t": context.tenant_id, "hours": body.support_hours},
    ).scalar_one()
    message = (
        f"{MARKER} Done-for-you move, session {session_id}. Came from: {origin}. "
        f"Files: {files}. Setup service {'included' if included else 'NOT bought (quote it)'}. "
        f"Support may look in until {expires:%Y-%m-%d %H:%M} UTC."
        + (f"\nNote from the owner: {body.note.strip()}" if body.note and body.note.strip() else "")
    )
    locale = db.execute(
        text("SELECT locale FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    try:
        with db.begin_nested():
            db.execute(
                text("SELECT app.submit_complaint(:message, :locale)"),
                {"message": message, "locale": locale},
            )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "P0001":
            raise HTTPException(status_code=429, detail="too_many_requests") from error
        raise
    _audit(context, "migration.concierge", {"session": str(session_id), "included": included})
    requested = _last(context, "migration.concierge", session_id)
    assert requested is not None
    return ConciergeOut(requested_at=requested[0], included=included, support_until=expires)
