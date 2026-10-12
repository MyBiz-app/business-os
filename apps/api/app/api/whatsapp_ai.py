"""AI replies on WhatsApp (module `whatsapp_ai`, app/messaging/whatsapp_ai.py): the business sees
its clients' conversations with the AI (`clients.read`) and can try the bot as one of its
clients (`business.settings`). A try runs the real flow on a test conversation: nothing is sent
and an accepted offer books nothing."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.gateway import LLMProvider, ProviderBusy, ProviderUnavailable, get_provider
from app.api.common import not_found
from app.api.deps import TenantContext, has_module, require
from app.core.permissions import Permission
from app.messaging import whatsapp_ai

router = APIRouter(prefix="/whatsapp-ai", tags=["whatsapp-ai"])


def _module(permission: Permission):
    def check(context: Annotated[TenantContext, Depends(require(permission))]) -> TenantContext:
        if not has_module(context.session, "whatsapp_ai"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
        return context

    return check


ReadDep = Annotated[TenantContext, Depends(_module(Permission.CLIENTS_READ))]
TryDep = Annotated[TenantContext, Depends(_module(Permission.BUSINESS_SETTINGS))]
ProviderDep = Annotated[LLMProvider | None, Depends(get_provider)]


class ConversationSummary(BaseModel):
    id: UUID
    phone: str
    client_id: UUID | None
    client_name: str | None
    last_text: str
    updated_at: dt.datetime


class Offer(BaseModel):
    id: UUID
    preview: dict[str, Any]
    status: Literal["pending", "accepted", "declined", "expired", "failed", "replaced"]
    expires_at: dt.datetime
    result: dict[str, Any] | None


class Turn(BaseModel):
    role: Literal["client", "ai"]
    text: str


class Conversation(BaseModel):
    id: UUID
    phone: str
    client_id: UUID | None
    turns: list[Turn]
    offers: list[Offer]
    updated_at: dt.datetime


class TryMessage(BaseModel):
    phone: str = Field(min_length=3, max_length=30, description="A client's phone number")
    text: str = Field(min_length=1, max_length=4000)


class TryReply(BaseModel):
    reply: str
    offer_id: UUID | None


def turns(messages: list[dict[str, Any]]) -> list[Turn]:
    """What the client wrote and what was sent back (each reply is the last model message of
    its turn; tool calls and the context lines are left out)."""
    result: list[Turn] = []
    for message in messages:
        blocks = message["content"] if isinstance(message["content"], list) else []
        words = [
            b["text"]
            for b in blocks
            if b.get("type") == "text" and not b["text"].startswith("<context>")
        ]
        if message["role"] == "user":
            if words and not any(b.get("type") == "tool_result" for b in blocks):
                result.append(Turn(role="client", text=words[-1]))
            continue
        reply = "\n\n".join(words).strip()
        if not reply:
            continue
        if result and result[-1].role == "ai":
            result[-1] = Turn(role="ai", text=reply)
        else:
            result.append(Turn(role="ai", text=reply))
    return result


def _load(db: Session, conversation_id: UUID) -> Conversation:
    row = (
        db.execute(
            text("""
                SELECT id, phone, client_id, messages, updated_at
                FROM app.whatsapp_conversations WHERE id = :id
            """),
            {"id": conversation_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    offers = [
        Offer.model_validate(dict(r))
        for r in db.execute(
            text("""
                SELECT id, preview, status, expires_at, result FROM app.whatsapp_offers
                WHERE conversation_id = :id ORDER BY created_at
            """),
            {"id": conversation_id},
        ).mappings()
    ]
    return Conversation(
        id=row["id"],
        phone=row["phone"],
        client_id=row["client_id"],
        turns=turns(row["messages"]),
        offers=offers,
        updated_at=row["updated_at"],
    )


@router.get("/conversations")
def list_whatsapp_conversations(context: ReadDep) -> list[ConversationSummary]:
    """The 50 most recent conversations with clients (tries are left out)."""
    rows = context.session.execute(
        text("""
            SELECT w.id, w.phone, w.client_id, w.messages, w.updated_at,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name
            FROM app.whatsapp_conversations w LEFT JOIN app.clients c ON c.id = w.client_id
            WHERE NOT w.test ORDER BY w.updated_at DESC LIMIT 50
        """)
    ).mappings()
    summaries = []
    for row in rows:
        said = turns(row["messages"])
        summaries.append(
            ConversationSummary(
                id=row["id"],
                phone=row["phone"],
                client_id=row["client_id"],
                client_name=row["client_name"],
                last_text=said[-1].text[:200] if said else "",
                updated_at=row["updated_at"],
            )
        )
    return summaries


@router.get("/conversations/{conversation_id}")
def get_whatsapp_conversation(conversation_id: UUID, context: ReadDep) -> Conversation:
    return _load(context.session, conversation_id)


@router.post("/try")
def try_bot(body: TryMessage, context: TryDep, provider: ProviderDep) -> TryReply:
    """Writes to the bot as the client with this phone number and returns its answer."""
    if provider is None or getattr(provider, "model", None) == "demo":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ai_not_configured"
        )
    try:
        reply = whatsapp_ai.handle(
            context.session, context.tenant_id, body.phone, body.text, provider, test=True
        )
    except ProviderBusy as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="ai_busy"
        ) from error
    except ProviderUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="ai_unavailable"
        ) from error
    if reply is None:
        raise HTTPException(status_code=422, detail="unknown_client")
    return TryReply(reply=reply.text, offer_id=reply.offer_id)


@router.delete("/try", status_code=status.HTTP_204_NO_CONTENT)
def reset_try(context: TryDep) -> None:
    """Starts the tries over (deletes the test conversations and their offers)."""
    context.session.execute(text("DELETE FROM app.whatsapp_conversations WHERE test"))
