"""Messaging (migration 0031), simulated: templates, broadcasts to a segment, direct messages
to a client or lead, and the message log. Needs the WhatsApp module; sending needs
`clients.write`, reading the log `clients.read`.

Texts may use {first_name} and {business}; each recipient gets the text with their own
values, which is what the log stores. Each message counts as usage (meter "messages")."""

import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, has_module, require
from app.metrics import members_at_risk
from app.permissions import Permission
from app.providers.choice import choose

router = APIRouter(prefix="/messages", tags=["messages"])

Channel = Literal["whatsapp", "sms"]
Audience = Literal["active", "inactive", "plan_ending", "no_plan", "open_leads"]
AUDIENCES: tuple[Audience, ...] = ("active", "inactive", "plan_ending", "no_plan", "open_leads")
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


class Recipient(BaseModel):
    client_id: UUID | None = None
    lead_id: UUID | None = None
    first_name: str
    phone: str


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
    recipients: int = Field(description="Who can be reached (has a phone number)")


class CampaignCreate(BaseModel):
    audience: Audience
    channel: Channel = "whatsapp"
    body: str = Field(min_length=1, max_length=MAX_BODY)
    dry_run: bool = Field(default=False, description="Only count and preview; send nothing")

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return _body(value)


class CampaignResult(BaseModel):
    id: UUID | None
    recipients: int
    preview: str | None = Field(description="The text as the first recipient gets it")


class Campaign(BaseModel):
    id: UUID
    audience: Audience
    channel: Channel
    body: str
    recipients: int
    created_at: datetime
    author_name: str | None


class DirectMessage(BaseModel):
    client_id: UUID | None = None
    lead_id: UUID | None = None
    channel: Channel = "whatsapp"
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
    channel: Channel
    to_phone: str
    body: str
    status: Literal["queued", "sent", "failed"]
    simulated: bool
    created_at: datetime


# --- Audiences --------------------------------------------------------------------------------


def _recipients(db: Session, audience: Audience) -> list[Recipient]:
    with_phone = "c.erased_at IS NULL AND c.phone IS NOT NULL AND trim(c.phone) <> ''"
    if audience == "open_leads":
        rows = db.execute(
            text("""
                SELECT id AS lead_id, first_name, phone FROM app.leads
                WHERE stage NOT IN ('won', 'lost') AND phone IS NOT NULL AND trim(phone) <> ''
                ORDER BY created_at
            """)
        ).mappings()
        return [Recipient.model_validate(dict(r)) for r in rows]
    if audience in ("inactive", "plan_ending"):
        ids = [
            m.client_id
            for m in members_at_risk(db, INACTIVE_DAYS, limit=5000)
            if m.reason == audience
        ]
        where = f"c.id = ANY(CAST(:ids AS uuid[])) AND {with_phone}"
        params: dict[str, object] = {"ids": ids}
    elif audience == "no_plan":
        where = f"""c.status = 'active' AND {with_phone} AND NOT EXISTS (
            SELECT 1 FROM app.entitlements e JOIN app.tenants t ON t.id = e.tenant_id
            WHERE e.client_id = c.id AND e.status = 'active'
              AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on)"""
        params = {}
    else:
        where = f"c.status = 'active' AND {with_phone}"
        params = {}
    rows = db.execute(
        text(f"""
            SELECT c.id AS client_id, c.first_name, c.phone FROM app.clients c
            WHERE {where} ORDER BY c.first_name, c.id
        """),
        params,
    ).mappings()
    return [Recipient.model_validate(dict(r)) for r in rows]


@router.get("/audiences")
def audiences(context: ReadDep) -> list[AudienceCount]:
    crm = has_module(context.session, "crm")
    return [
        AudienceCount(audience=a, recipients=len(_recipients(context.session, a)))
        for a in AUDIENCES
        if a != "open_leads" or crm
    ]


# --- Sending ----------------------------------------------------------------------------------


def _business(db: Session) -> str:
    return db.execute(
        text("SELECT name FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()


def render(body: str, first_name: str, business: str) -> str:
    """Fills {first_name} and {business}; other braces are left as typed."""
    return body.replace("{first_name}", first_name).replace("{business}", business)


def _send(
    context: TenantContext,
    recipients: list[Recipient],
    channel: Channel,
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
            "to_phone": r.phone.strip(),
            "body": render(body, r.first_name, business),
        }
        for r in recipients
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


@router.post("/campaigns")
def send_campaign(body: CampaignCreate, context: SendDep) -> CampaignResult:
    """Sends the text to everyone in the audience who has a phone number (or previews it)."""
    db = context.session
    if body.audience == "open_leads" and not has_module(db, "crm"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    recipients = _recipients(db, body.audience)
    preview = render(body.body, recipients[0].first_name, _business(db)) if recipients else None
    if body.dry_run or not recipients:
        return CampaignResult(id=None, recipients=len(recipients), preview=preview)
    campaign_id = db.execute(
        text("""
            INSERT INTO app.campaigns (tenant_id, audience, channel, body, recipients, created_by)
            VALUES (:t, :audience, :channel, :body, :n, app.current_user_id()) RETURNING id
        """),
        {
            "t": context.tenant_id,
            "audience": body.audience,
            "channel": body.channel,
            "body": body.body,
            "n": len(recipients),
        },
    ).scalar_one()
    _send(context, recipients, body.channel, body.body, campaign_id)
    return CampaignResult(id=campaign_id, recipients=len(recipients), preview=preview)


@router.get("/campaigns")
def list_campaigns(context: ReadDep) -> list[Campaign]:
    rows = context.session.execute(
        text("""
            SELECT c.id, c.audience, c.channel, c.body, c.recipients, c.created_at,
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
