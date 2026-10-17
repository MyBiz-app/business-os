"""The broadcast center (round 5, M1; migration 0100): the MyBiz console composes a message for a
mix of audiences and channels, previews who gets it, schedules it and reads the results. People
see the pop-ups meant for them and can opt out of marketing messages. The sending itself is the
send-announcements job (app/messaging/announcements.py)."""

import datetime as dt
import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import AnonymousSessionDep, SessionDep
from app.api.platform import PlatformPermission, require_platform, run_rule
from app.core.signed_links import verify
from app.messaging.announcements import _email, content_for
from app.messaging.consent import request_origin
from app.messaging.email import load_messages, sender_from_settings

router = APIRouter(tags=["broadcasts"])

BroadcastsDep = Annotated[Session, Depends(require_platform(PlatformPermission.BROADCASTS_MANAGE))]

Channel = Literal["email", "push", "popup", "whatsapp", "sms"]
Group = Literal["team", "owners", "staff", "clients"]
Locale = Literal["he", "en"]


class Texts(BaseModel):
    subject: str = Field(default="", max_length=150)
    body: str = Field(default="", max_length=4000)
    cta_label: str = Field(default="", max_length=60)
    cta_url: str = Field(default="", max_length=500)
    image_url: str = Field(default="", max_length=500)

    @field_validator("cta_url", "image_url")
    @classmethod
    def web_address(cls, value: str) -> str:
        if value and not value.startswith(("https://", "http://", "/")):
            raise ValueError("must be a web address")
        return value


class Audience(BaseModel):
    groups: list[Group] = Field(default_factory=list, max_length=4)
    verticals: list[str] = Field(default_factory=list, max_length=60)
    locales: list[Locale] = Field(default_factory=list, max_length=2)
    business_ids: list[UUID] = Field(default_factory=list, max_length=500)
    modules: list[str] = Field(default_factory=list, max_length=60)
    status: Literal["trial", "active"] | None = None


class StoredAudience(BaseModel):
    """An audience as stored: every key is present."""

    groups: list[Group]
    verticals: list[str]
    locales: list[Locale]
    business_ids: list[UUID]
    modules: list[str]
    status: Literal["trial", "active"] | None


class AnnouncementBody(BaseModel):
    kind: Literal["marketing", "service"]
    channels: list[Channel] = Field(min_length=1, max_length=5)
    audience: Audience
    content: dict[Locale, Texts] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def distinct(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class DeliveryStats(BaseModel):
    queued: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    viewed: int = 0
    clicked: int = 0
    unsubscribed: int = 0
    sent_by_channel: dict[str, int] = Field(default_factory=dict)


class Announcement(BaseModel):
    id: UUID
    kind: Literal["marketing", "service"]
    channels: list[Channel]
    audience: StoredAudience
    content: dict[Locale, Texts]
    scheduled_at: dt.datetime | None
    status: Literal["draft", "scheduled", "sending", "sent", "cancelled"]
    recipient_count: int | None
    created_by: str
    created_at: dt.datetime
    sent_at: dt.datetime | None
    stats: DeliveryStats


class Preview(BaseModel):
    total: int
    email: int
    push: int
    popup: int
    phone: int
    by_group: dict[str, int]


class PreviewBody(BaseModel):
    kind: Literal["marketing", "service"]
    audience: Audience


class ScheduleBody(BaseModel):
    scheduled_at: dt.datetime | None = Field(
        default=None, description="When to send; empty sends at the next job run"
    )


class TestResult(BaseModel):
    sent_to: str
    email: bool


def _json(model: BaseModel | dict[str, Any]) -> str:
    if isinstance(model, BaseModel):
        return model.model_dump_json()
    return json.dumps(model)


def _content_json(content: dict[Locale, Texts]) -> str:
    return json.dumps({locale: texts.model_dump() for locale, texts in content.items()})


def _call(db: Session, sql: str, params: dict[str, Any]) -> Any:
    """Calls a console function; its rules become HTTP errors."""
    try:
        with db.begin_nested():
            return db.execute(text(sql), params)
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        detail = str(getattr(getattr(error.orig, "diag", None), "message_primary", "")) or "error"
        statuses = {"42501": 403, "P0002": 404, "P0003": 409, "P0001": 422}
        if code in statuses:
            raise HTTPException(status_code=statuses[code], detail=detail) from error
        raise


def _read(db: Session, one: UUID | None = None) -> list[Announcement]:
    rows = _call(db, "SELECT * FROM app.announcement_rows(:one)", {"one": one}).mappings().all()
    return [Announcement.model_validate(dict(row)) for row in rows]


def _one(db: Session, announcement_id: UUID) -> Announcement:
    found = _read(db, one=announcement_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return found[0]


def _me(db: Session) -> str:
    return db.execute(text("SELECT email FROM app.platform_me()")).scalar_one()


def _save(db: Session, announcement_id: UUID | None, body: AnnouncementBody) -> UUID:
    return _call(
        db,
        """
        SELECT app.announcement_save(:id, :kind, :channels, CAST(:audience AS jsonb),
                                     CAST(:content AS jsonb))
        """,
        {
            "id": announcement_id,
            "kind": body.kind,
            "channels": body.channels,
            "audience": body.audience.model_dump_json(),
            "content": _content_json(body.content),
        },
    ).scalar_one()


@router.get("/platform/broadcasts")
def list_broadcasts(db: BroadcastsDep) -> list[Announcement]:
    return _read(db)


@router.post("/platform/broadcasts/preview")
def preview(body: PreviewBody, db: BroadcastsDep) -> Preview:
    """Who would get it right now: people counted once however many groups they are in."""
    result = db.execute(
        text("SELECT app.announcement_preview(CAST(:audience AS jsonb), :kind)"),
        {"audience": body.audience.model_dump_json(), "kind": body.kind},
    ).scalar_one()
    return Preview.model_validate(result)


@router.post("/platform/broadcasts", status_code=status.HTTP_201_CREATED)
def create_broadcast(body: AnnouncementBody, db: BroadcastsDep) -> Announcement:
    return _one(db, _save(db, None, body))


@router.get("/platform/broadcasts/{announcement_id}")
def get_broadcast(announcement_id: UUID, db: BroadcastsDep) -> Announcement:
    return _one(db, announcement_id)


@router.put("/platform/broadcasts/{announcement_id}")
def update_broadcast(
    announcement_id: UUID, body: AnnouncementBody, db: BroadcastsDep
) -> Announcement:
    """Only a draft or a scheduled message can still be changed; a scheduled one goes back to
    a draft, so it is checked again before it is scheduled."""
    _save(db, announcement_id, body)
    return _one(db, announcement_id)


def _ready(announcement: Announcement) -> None:
    """A message that can go out: someone to send to, and words in at least one language."""
    if not announcement.audience.groups:
        raise HTTPException(status_code=422, detail="audience_required")
    if not any(t.subject.strip() and t.body.strip() for t in announcement.content.values()):
        raise HTTPException(status_code=422, detail="content_required")


@router.post("/platform/broadcasts/{announcement_id}/schedule")
def schedule_broadcast(
    announcement_id: UUID, body: ScheduleBody, db: BroadcastsDep
) -> Announcement:
    _ready(_one(db, announcement_id))
    _call(
        db,
        "SELECT app.announcement_schedule(:id, :at)",
        {"id": announcement_id, "at": body.scheduled_at},
    )
    return _one(db, announcement_id)


@router.post("/platform/broadcasts/{announcement_id}/cancel")
def cancel_broadcast(announcement_id: UUID, db: BroadcastsDep) -> Announcement:
    _call(db, "SELECT app.announcement_cancel(:id)", {"id": announcement_id})
    return _one(db, announcement_id)


@router.delete("/platform/broadcasts/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_broadcast(announcement_id: UUID, db: BroadcastsDep) -> Response:
    _call(db, "SELECT app.announcement_delete(:id)", {"id": announcement_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/platform/broadcasts/{announcement_id}/test")
def send_test(announcement_id: UUID, db: BroadcastsDep) -> TestResult:
    """Sends the email version to the signed-in team member alone, to see how it looks."""
    announcement = _one(db, announcement_id)
    me = _me(db)
    locale = (
        db.execute(
            text("SELECT coalesce(u.locale, 'he') FROM app.users u WHERE lower(u.email) = :e"),
            {"e": me},
        ).scalar()
        or "he"
    )
    lang = locale if locale in ("he", "en") else "he"
    content = {k: v.model_dump() for k, v in announcement.content.items()}
    texts = content_for(content, lang)
    if not texts["subject"] and not texts["body"]:
        raise HTTPException(status_code=422, detail="content_required")
    sender = sender_from_settings()
    if sender is None:
        return TestResult(sent_to=me, email=False)
    row = {
        "email": me,
        "kind": announcement.kind,
        "announcement_id": announcement_id,
        "locale": lang,
    }
    sender.send(_email(row, texts, load_messages(lang)))
    return TestResult(sent_to=me, email=True)


class MyAnnouncement(BaseModel):
    id: UUID
    kind: Literal["marketing", "service"]
    texts: Texts
    sent_at: dt.datetime | None


@router.get("/me/announcements", tags=["account"])
def my_announcements(db: SessionDep) -> list[MyAnnouncement]:
    """The pop-ups meant for the signed-in person, not yet dismissed, in their language."""
    rows = db.execute(text("SELECT * FROM app.my_announcements()")).mappings().all()
    return [
        MyAnnouncement(
            id=row["id"],
            kind=row["kind"],
            texts=Texts.model_validate(content_for(row["content"], row["locale"])),
            sent_at=row["sent_at"],
        )
        for row in rows
    ]


@router.post(
    "/me/announcements/{announcement_id}/{event}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["account"],
)
def mark_announcement(
    announcement_id: UUID, event: Literal["viewed", "dismissed", "clicked"], db: SessionDep
) -> Response:
    run_rule(
        db,
        "SELECT app.announcement_mark(:id, :event)",
        {"id": announcement_id, "event": event},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ConsentBody(BaseModel):
    consent: bool
    source: Literal["app_join", "app_profile"] = Field(
        default="app_profile", description="Where the person chose: when joining, or in the profile"
    )


@router.put("/me/marketing-consent", status_code=status.HTTP_204_NO_CONTENT, tags=["account"])
def set_marketing_consent(body: ConsentBody, request: Request, db: SessionDep) -> Response:
    """Agree to (or stop) marketing messages; service messages are sent either way. Each change
    is kept with its time, source and device."""
    address, device = request_origin(request)
    db.execute(
        text("SELECT app.set_marketing_consent(:consent, :source, :ip, :ua)"),
        {"consent": body.consent, "source": body.source, "ip": address, "ua": device},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _opt_out_page(ok: bool) -> HTMLResponse:
    messages = load_messages("he")["broadcast"], load_messages("en")["broadcast"]
    sections = ""
    for lang, m in zip(("he", "en"), messages, strict=True):
        direction = "rtl" if lang == "he" else "ltr"
        title = escape(m["unsubscribedTitle"] if ok else m["unsubscribeFailed"])
        detail = f"<p>{escape(m['unsubscribedBody'])}</p>" if ok else ""
        sections += f'<section lang="{lang}" dir="{direction}"><h1>{title}</h1>{detail}</section>'
    page = (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        "<title>MyBiz</title>"
        '<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;'
        f'padding:0 1rem">{sections}</body>'
    )
    return HTMLResponse(page, status_code=200 if ok else 400)


def _unsubscribe_signed(t: str, db: Session) -> bool:
    subject = verify(t)
    parts = subject.split("|") if subject else []
    if not (len(parts) == 3 and parts[0] == "unsub"):
        return False
    email, announcement = parts[1], parts[2]
    try:
        announcement_id: UUID | None = UUID(announcement)
    except ValueError:
        announcement_id = None
    db.execute(
        text("SELECT app.marketing_unsubscribe(:email, :announcement)"),
        {"email": email, "announcement": announcement_id},
    )
    return True


@router.get("/public/announcements/unsubscribe", response_class=HTMLResponse, tags=["account"])
def unsubscribe(t: Annotated[str, Query(max_length=600)], db: AnonymousSessionDep) -> HTMLResponse:
    """The opt-out link in a marketing email (the link is signed; no sign-in needed)."""
    return _opt_out_page(_unsubscribe_signed(t, db))


@router.post("/public/announcements/unsubscribe", tags=["account"])
def unsubscribe_one_click_signed(
    t: Annotated[str, Query(max_length=600)], db: AnonymousSessionDep
) -> Response:
    """The mail app's own "Unsubscribe" button (RFC 8058 one-click) on the same signed link."""
    ok = _unsubscribe_signed(t, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT if ok else status.HTTP_400_BAD_REQUEST)


@router.get("/u/{token}", response_class=HTMLResponse, tags=["account"])
def unsubscribe_by_link(token: str, request: Request, db: AnonymousSessionDep) -> HTMLResponse:
    """The short opt-out link of an ad sent by a business (SMS, WhatsApp, email): one tap, no
    sign-in. It stops that business's ads for that client and is kept in the consent trail."""
    if not 8 <= len(token) <= 64:
        return _opt_out_page(False)
    address, device = request_origin(request)
    business = db.execute(
        text("SELECT app.unsubscribe_by_token(:token, :ip, :ua)"),
        {"token": token, "ip": address, "ua": device},
    ).scalar()
    return _opt_out_page(business is not None)


@router.post("/u/{token}", status_code=status.HTTP_204_NO_CONTENT, tags=["account"])
def unsubscribe_one_click(token: str, request: Request, db: AnonymousSessionDep) -> Response:
    """The mail app's own "Unsubscribe" button (RFC 8058 one-click)."""
    if 8 <= len(token) <= 64:
        address, device = request_origin(request)
        db.execute(
            text("SELECT app.unsubscribe_by_token(:token, :ip, :ua)"),
            {"token": token, "ip": address, "ua": device},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
