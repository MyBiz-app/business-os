"""Messaging (migration 0031), simulated: templates, broadcasts to a segment, direct messages
to a client or lead, and the message log. Needs the WhatsApp module; sending needs
`clients.write`, reading the log `clients.read`.

Texts may use the variables of app/messaging/placeholders.py ({first_name}, {plan_name|fallback},
...); each recipient gets the text with their own values, which is what the log stores. Each
message counts as usage (meter "messages").

A campaign can be aimed at some of the business's branches (round 5, F4): the clients who belong
to them (their home branch or "my branches" list), or the staff who work in them. WhatsApp and SMS
go through the business's outbox; email, push and pop-up go through the broadcast engine
(app/messaging/announcements.py). Someone kept to some branches reaches only those."""

import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, ensure_branch_allowed, has_module, require
from app.core.permissions import Permission
from app.messaging.placeholders import (
    GROUPS,
    SAMPLE,
    client_values,
    lead_values,
    missing_counts,
    render_placeholders,
)
from app.providers.choice import choose
from app.reports.metrics import members_at_risk

router = APIRouter(prefix="/messages", tags=["messages"])

PhoneChannel = Literal["whatsapp", "sms"]
Channel = Literal["whatsapp", "sms", "email", "push", "popup"]
PHONE_CHANNELS = ("whatsapp", "sms")
NET_CHANNELS = ("email", "push", "popup")  # sent by the broadcast engine
Audience = Literal["active", "inactive", "plan_ending", "no_plan", "open_leads", "staff"]
AUDIENCES: tuple[Audience, ...] = (
    "active",
    "inactive",
    "plan_ending",
    "no_plan",
    "open_leads",
    "staff",
)
INACTIVE_DAYS = 14
MAX_BODY = 1000


def _messaging(permission: Permission):
    def check(context: Annotated[TenantContext, Depends(require(permission))]) -> TenantContext:
        if not has_module(context.session, "whatsapp"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
        return context

    return check


ReadDep = Annotated[TenantContext, Depends(_messaging(Permission.CLIENTS_READ))]
SendDep = Annotated[TenantContext, Depends(_messaging(Permission.CLIENTS_WRITE))]
# Email, push and pop-up need no WhatsApp module: only the phone channels do (checked per request).
ReadAnyDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
SendAnyDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]


def _need_module(db: Session, channels: list["Channel"]) -> None:
    if any(c in PHONE_CHANNELS for c in channels) and not has_module(db, "whatsapp"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")


class Recipient(BaseModel):
    client_id: UUID | None = None
    lead_id: UUID | None = None
    user_id: UUID | None = None  # the account behind a client, or the staff member
    first_name: str
    phone: str | None = None
    email: str | None = None


def _body(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("body must not be blank")
    return value


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=MAX_BODY)

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return _body(value)


class Template(BaseModel):
    id: UUID
    name: str
    body: str
    created_at: datetime


class AudienceCount(BaseModel):
    audience: Audience
    recipients: int = Field(description="Who can be reached on at least one of the channels")
    by_channel: dict[str, int] = Field(
        default_factory=dict, description="How many can be reached on each channel"
    )


class CampaignCreate(BaseModel):
    audience: Audience
    channel: Channel = "whatsapp"
    channels: list[Channel] | None = Field(
        default=None, max_length=5, description="Several channels at once; overrides `channel`"
    )
    location_ids: list[UUID] | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Only the clients (or staff) of these branches; null = the whole network",
    )
    subject: str | None = Field(
        default=None, max_length=150, description="Email subject and push/pop-up title"
    )
    promotional: bool = Field(
        default=False,
        description="An advertisement: goes only to people who agreed to receive them",
    )
    dry_run: bool = Field(default=False, description="Only count and preview; send nothing")
    body: str = Field(min_length=1, max_length=MAX_BODY)

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return _body(value)


class PlaceholderWarning(BaseModel):
    variable: str
    recipients: int = Field(description="How many recipients have no value and no fallback")


class CampaignResult(BaseModel):
    id: UUID | None
    recipients: int
    by_channel: dict[str, int] = Field(default_factory=dict)
    preview: str | None = Field(description="The text as the first recipient gets it")
    warnings: list[PlaceholderWarning] = Field(
        default_factory=list,
        description="Variables some recipients have no value for (set a fallback with {name|text})",
    )


class PlaceholderGroup(BaseModel):
    key: str
    variables: list[str]


class Placeholders(BaseModel):
    groups: list[PlaceholderGroup]
    sample: dict[str, str] = Field(description="Values of a made-up client, for the preview")


class Campaign(BaseModel):
    id: UUID
    audience: Audience
    channel: Channel
    channels: list[Channel]
    location_ids: list[UUID] | None
    body: str
    recipients: int
    created_at: datetime
    author_name: str | None


class DirectMessage(BaseModel):
    client_id: UUID | None = None
    lead_id: UUID | None = None
    channel: PhoneChannel = "whatsapp"
    body: str = Field(min_length=1, max_length=MAX_BODY)

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return _body(value)

    @model_validator(mode="after")
    def one_recipient(self) -> "DirectMessage":
        if (self.client_id is None) == (self.lead_id is None):
            raise ValueError("give exactly one of client_id, lead_id")
        return self


class Message(BaseModel):
    id: UUID
    campaign_id: UUID | None
    client_id: UUID | None
    lead_id: UUID | None
    recipient_name: str | None
    channel: PhoneChannel
    to_phone: str
    body: str
    status: Literal["queued", "sent", "failed"]
    simulated: bool
    created_at: datetime


# --- Audiences --------------------------------------------------------------------------------

BRANCH_BOUND = frozenset({"branch_manager"})


def _scope(context: TenantContext, location_ids: list[UUID] | None) -> list[UUID] | None:
    """The branches a message is aimed at; None = no branch filter. Someone kept to some
    branches can never reach beyond them, and by default reaches all of theirs."""
    if location_ids is None:
        return sorted(context.branches) if context.branches is not None else None
    for location_id in location_ids:
        ensure_branch_allowed(context, location_id)
    known = context.session.execute(
        text("SELECT count(*) FROM app.locations WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": list(location_ids)},
    ).scalar_one()
    if known != len(set(location_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_branch"
        )
    return list(location_ids)


def _channels(channel: Channel, channels: list[Channel] | None) -> list[Channel]:
    return list(dict.fromkeys(channels or [channel]))


def _reach(channels: list[Channel], phone: str, email: str, account: str) -> str:
    """SQL: the person can be reached on at least one of the channels."""
    parts = []
    if any(c in PHONE_CHANNELS for c in channels):
        parts.append(f"({phone} IS NOT NULL AND trim({phone}) <> '')")
    if "email" in channels:
        parts.append(f"({email} IS NOT NULL AND trim({email}) <> '')")
    if any(c in ("push", "popup") for c in channels):
        parts.append(f"{account} IS NOT NULL")
    return "(" + " OR ".join(parts) + ")"


def _people(
    db: Session,
    audience: Audience,
    channels: list[Channel],
    scope: list[UUID] | None,
    promotional: bool = False,
) -> list[Recipient]:
    """Who the message reaches: the audience, in the chosen branches, on any chosen channel."""
    params: dict[str, object] = {"locs": scope}
    if audience == "staff":
        # Owners and managers work in every branch; others in the branches on their list (none
        # listed = all, except for a branch manager, who has only their own).
        rows = db.execute(
            text("""
                SELECT u.id AS user_id, lower(u.email) AS email,
                       coalesce(nullif(split_part(trim(u.full_name), ' ', 1), ''),
                                split_part(u.email, '@', 1)) AS first_name
                FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                WHERE (CAST(:locs AS uuid[]) IS NULL
                       OR m.role IN ('owner', 'manager')
                       OR (cardinality(m.location_ids) = 0
                           AND NOT (m.role = ANY(CAST(:bound AS text[]))))
                       OR m.location_ids && CAST(:locs AS uuid[]))
                  AND (NOT CAST(:promo AS boolean) OR u.marketing_consent_at IS NOT NULL)
                ORDER BY first_name, u.id
            """),
            {**params, "bound": list(BRANCH_BOUND), "promo": promotional},
        ).mappings()
        return [Recipient.model_validate(dict(r)) for r in rows]
    consent = (
        """AND (c.marketing_consent_at IS NOT NULL OR EXISTS (
                 SELECT 1 FROM app.users cu
                 WHERE cu.id = c.user_id AND cu.marketing_consent_at IS NOT NULL))"""
        if promotional
        else ""
    )
    if audience == "open_leads":
        rows = db.execute(
            text("""
                SELECT id AS lead_id, first_name, phone FROM app.leads
                WHERE stage NOT IN ('won', 'lost') AND phone IS NOT NULL AND trim(phone) <> ''
                ORDER BY created_at
            """)
        ).mappings()
        return [Recipient.model_validate(dict(r)) for r in rows]
    where = (
        f"c.erased_at IS NULL AND {_reach(channels, 'c.phone', 'c.email', 'c.user_id')} {consent}"
    )
    if scope is not None:
        where += """ AND (c.home_location_id = ANY(CAST(:locs AS uuid[])) OR EXISTS (
            SELECT 1 FROM app.client_locations cl
            WHERE cl.client_id = c.id AND cl.location_id = ANY(CAST(:locs AS uuid[]))))"""
    if audience in ("inactive", "plan_ending"):
        ids = [
            m.client_id
            for m in members_at_risk(db, INACTIVE_DAYS, limit=5000)
            if m.reason == audience
        ]
        where += " AND c.id = ANY(CAST(:ids AS uuid[]))"
        params["ids"] = ids
    elif audience == "no_plan":
        where += """ AND c.status = 'active' AND NOT EXISTS (
            SELECT 1 FROM app.entitlements e JOIN app.tenants t ON t.id = e.tenant_id
            WHERE e.client_id = c.id AND e.status = 'active'
              AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on)"""
    else:
        where += " AND c.status = 'active'"
    rows = db.execute(
        text(f"""
            SELECT c.id AS client_id, c.user_id, c.first_name, c.phone, lower(c.email) AS email
            FROM app.clients c WHERE {where} ORDER BY c.first_name, c.id
        """),
        params,
    ).mappings()
    return [Recipient.model_validate(dict(r)) for r in rows]


def _with_push(db: Session, people: list[Recipient]) -> set[UUID]:
    ids = [p.user_id for p in people if p.user_id]
    if not ids:
        return set()
    return set(
        db.execute(text("SELECT app.users_with_push(CAST(:ids AS uuid[]))"), {"ids": ids}).scalars()
    )


def _by_channel(db: Session, people: list[Recipient], channels: list[Channel]) -> dict[str, int]:
    pushable = _with_push(db, people) if "push" in channels else set()
    counts: dict[str, int] = {}
    for channel in channels:
        if channel in PHONE_CHANNELS:
            n = sum(1 for p in people if p.phone and p.phone.strip())
        elif channel == "email":
            n = sum(1 for p in people if p.email and p.email.strip())
        elif channel == "popup":
            n = sum(1 for p in people if p.user_id)
        else:
            n = sum(1 for p in people if p.user_id in pushable)
        counts[channel] = n
    return counts


@router.get("/placeholders")
def placeholders(context: ReadAnyDep) -> Placeholders:
    """The variables a message may use, grouped, with sample values for the live preview."""
    return Placeholders(
        groups=[PlaceholderGroup(key=k, variables=list(v)) for k, v in GROUPS.items()],
        sample={**SAMPLE, "business": _business(context.session)},
    )


@router.get("/audiences")
def audiences(
    context: ReadAnyDep,
    location_ids: Annotated[list[UUID] | None, Query()] = None,
    channels: Annotated[list[Channel] | None, Query()] = None,
) -> list[AudienceCount]:
    crm = has_module(context.session, "crm")
    chosen = _channels("whatsapp", channels)
    _need_module(context.session, chosen)
    scope = _scope(context, location_ids)
    counts = []
    for a in AUDIENCES:
        if a == "open_leads" and (not crm or location_ids is not None):
            continue  # leads belong to no branch
        people = _people(context.session, a, chosen, scope)
        counts.append(
            AudienceCount(
                audience=a,
                recipients=len(people),
                by_channel=_by_channel(context.session, people, chosen),
            )
        )
    return counts


# --- Sending ----------------------------------------------------------------------------------


def _business(db: Session) -> str:
    return db.execute(
        text("SELECT name FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()


def _values(
    db: Session, tenant_id: UUID, people: list[Recipient], business: str
) -> list[dict[str, str]]:
    """The placeholder values of each recipient, in order."""
    known = client_values(db, tenant_id, [p.client_id for p in people if p.client_id], business)
    return [
        known.get(p.client_id)
        if p.client_id and p.client_id in known
        else lead_values({"first_name": p.first_name, "phone": p.phone, "email": p.email}, business)
        for p in people
    ]


def render(body: str, person: dict[str, str]) -> str:
    return render_placeholders(body, person)


def _send(
    context: TenantContext,
    recipients: list[Recipient],
    channel: PhoneChannel,
    body: str,
    campaign_id: UUID | None,
) -> None:
    db = context.session
    business = _business(db)
    rows = [
        {
            "tenant_id": context.tenant_id,
            "campaign_id": campaign_id,
            "client_id": r.client_id,
            "lead_id": r.lead_id,
            "channel": channel,
            "to_phone": (r.phone or "").strip(),
            "body": render(body, values),
        }
        for r, values in zip(
            recipients, _values(db, context.tenant_id, recipients, business), strict=True
        )
    ]
    if not rows:
        return
    # The business's messaging provider (X13): the simulated one marks them sent now; a real
    # one gets them from the outbox (status queued) in the send-messages job.
    chosen = choose(db, context.tenant_id, "messaging")
    simulated = chosen.instance.simulated
    db.execute(
        text("""
            INSERT INTO app.messages
                (tenant_id, campaign_id, client_id, lead_id, channel, to_phone, body, status,
                 simulated, provider, sent_at, created_by)
            VALUES (:tenant_id, :campaign_id, :client_id, :lead_id, :channel, :to_phone, :body,
                    :status, :simulated, :provider, CASE WHEN :simulated THEN now() END,
                    app.current_user_id())
        """),
        [
            {
                **row,
                "status": "sent" if simulated else "queued",
                "simulated": simulated,
                "provider": chosen.info.name,
            }
            for row in rows
        ],
    )
    db.execute(
        text("""
            INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
            VALUES (:t, 'messages', :quantity, :details, :ref)
        """),
        {
            "t": context.tenant_id,
            "quantity": len(rows),
            "details": json.dumps({"channel": channel, "simulated": simulated}),
            "ref": str(campaign_id) if campaign_id else None,
        },
    )


def _unreachable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _announce(
    context: TenantContext,
    people: list[Recipient],
    channels: list[Channel],
    body: CampaignCreate,
    scope: list[UUID] | None,
    business: str,
) -> None:
    """Email, push and pop-up: one business announcement the broadcast engine sends."""
    text_ = {"subject": (body.subject or business).strip(), "body": body.body}
    audience = {
        "client_ids": [str(p.client_id) for p in people if p.client_id],
        "user_ids": [str(p.user_id) for p in people if p.user_id and not p.client_id],
        # One branch keeps its own contact addresses as the sender and Reply-To.
        "location_id": str(scope[0]) if scope and len(scope) == 1 else None,
    }
    context.session.execute(
        text("""
            SELECT app.tenant_announcement_create(
                :kind, CAST(:channels AS text[]), CAST(:audience AS jsonb), CAST(:content AS jsonb))
        """),
        {
            "kind": "marketing" if body.promotional else "service",
            "channels": list(channels),
            "audience": json.dumps(audience),
            "content": json.dumps({"he": text_, "en": text_}),
        },
    )


@router.post("/campaigns")
def send_campaign(body: CampaignCreate, context: SendAnyDep) -> CampaignResult:
    """Sends the text to everyone in the audience (in the chosen branches) who can be reached on
    the chosen channels (or previews it)."""
    db = context.session
    channels = _channels(body.channel, body.channels)
    phone = [c for c in channels if c in PHONE_CHANNELS]
    net = [c for c in channels if c in NET_CHANNELS]
    if body.audience != "staff":
        _need_module(db, channels)
    if body.audience == "open_leads":
        if not has_module(db, "crm"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
        if body.location_ids is not None:
            raise _unreachable("leads_have_no_branch")
        if net:
            raise _unreachable("leads_phone_only")
    if body.audience == "staff":
        if not net:
            raise _unreachable("staff_channels")
        channels, phone = net, []
    scope = _scope(context, body.location_ids)
    people = _people(db, body.audience, channels, scope, body.promotional)
    business = _business(db)
    values = _values(db, context.tenant_id, people, business)
    preview = render(body.body, values[0]) if people else None
    warnings = [
        PlaceholderWarning(variable=name, recipients=n)
        for name, n in missing_counts(body.body, values).items()
    ]
    by_channel = _by_channel(db, people, channels)
    if body.dry_run or not people:
        return CampaignResult(
            id=None,
            recipients=len(people),
            by_channel=by_channel,
            preview=preview,
            warnings=warnings,
        )
    campaign_id = db.execute(
        text("""
            INSERT INTO app.campaigns
                (tenant_id, audience, channel, channels, location_ids, body, recipients,
                 created_by)
            VALUES (:t, :audience, :channel, :channels, :locs, :body, :n, app.current_user_id())
            RETURNING id
        """),
        {
            "t": context.tenant_id,
            "audience": body.audience,
            "channel": channels[0],
            "channels": channels,
            "locs": body.location_ids,
            "body": body.body,
            "n": len(people),
        },
    ).scalar_one()
    for channel in phone:
        reachable = [p for p in people if p.phone and p.phone.strip()]
        _send(context, reachable, channel, body.body, campaign_id)
    if net:
        _announce(context, people, net, body, scope, business)
    return CampaignResult(
        id=campaign_id,
        recipients=len(people),
        by_channel=by_channel,
        preview=preview,
        warnings=warnings,
    )


@router.get("/campaigns")
def list_campaigns(context: ReadAnyDep) -> list[Campaign]:
    rows = context.session.execute(
        text("""
            SELECT c.id, c.audience, c.channel, coalesce(c.channels, ARRAY[c.channel]) AS channels,
                   c.location_ids, c.body, c.recipients, c.created_at,
                   coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1))
                       AS author_name
            FROM app.campaigns c LEFT JOIN app.users u ON u.id = c.created_by
            ORDER BY c.created_at DESC LIMIT 100
        """)
    ).mappings()
    return [Campaign.model_validate(dict(r)) for r in rows]


@router.post("/direct", status_code=status.HTTP_201_CREATED)
def send_direct(body: DirectMessage, context: SendDep) -> Message:
    db = context.session
    if body.client_id:
        row = (
            db.execute(
                text("""
                SELECT id AS client_id, first_name, phone FROM app.clients
                WHERE id = :id AND erased_at IS NULL
            """),
                {"id": body.client_id},
            )
            .mappings()
            .first()
        )
    else:
        row = (
            db.execute(
                text("SELECT id AS lead_id, first_name, phone FROM app.leads WHERE id = :id"),
                {"id": body.lead_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        raise not_found()
    if not (row["phone"] or "").strip():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_phone")
    _send(context, [Recipient.model_validate(dict(row))], body.channel, body.body, None)
    return _log(db, client_id=body.client_id, lead_id=body.lead_id, limit=1)[0]


# --- Log and templates ------------------------------------------------------------------------


def _log(
    db: Session,
    client_id: UUID | None = None,
    lead_id: UUID | None = None,
    campaign_id: UUID | None = None,
    limit: int = 200,
) -> list[Message]:
    where, params = "TRUE", {"limit": limit}
    filters = {"client_id": client_id, "lead_id": lead_id, "campaign_id": campaign_id}
    for column, value in filters.items():
        if value is not None:
            where += f" AND m.{column} = :{column}"
            params[column] = value
    rows = db.execute(
        text(f"""
            SELECT m.id, m.campaign_id, m.client_id, m.lead_id, m.channel, m.to_phone, m.body,
                   m.status, m.simulated, m.created_at,
                   coalesce(c.first_name || coalesce(' ' || c.last_name, ''),
                            l.first_name || coalesce(' ' || l.last_name, '')) AS recipient_name
            FROM app.messages m
            LEFT JOIN app.clients c ON c.id = m.client_id
            LEFT JOIN app.leads l ON l.id = m.lead_id
            WHERE {where} ORDER BY m.created_at DESC, m.id LIMIT :limit
        """),
        params,
    ).mappings()
    return [Message.model_validate(dict(r)) for r in rows]


@router.get("")
def message_log(
    context: ReadDep,
    client_id: UUID | None = None,
    lead_id: UUID | None = None,
    campaign_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[Message]:
    return _log(context.session, client_id, lead_id, campaign_id, limit)


@router.get("/templates")
def list_templates(context: ReadDep) -> list[Template]:
    rows = context.session.execute(
        text("SELECT id, name, body, created_at FROM app.message_templates ORDER BY name")
    ).mappings()
    return [Template.model_validate(dict(r)) for r in rows]


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_template(body: TemplateCreate, context: SendDep) -> Template:
    row = (
        context.session.execute(
            text("""
            INSERT INTO app.message_templates (tenant_id, name, body) VALUES (:t, :name, :body)
            RETURNING id, name, body, created_at
        """),
            {"t": context.tenant_id, "name": body.name.strip(), "body": body.body},
        )
        .mappings()
        .one()
    )
    return Template.model_validate(dict(row))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, context: SendDep) -> None:
    deleted = context.session.execute(
        text("DELETE FROM app.message_templates WHERE id = :id RETURNING id"), {"id": template_id}
    ).scalar()
    if deleted is None:
        raise not_found()
