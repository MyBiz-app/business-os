"""Conversation storage, token budget and accepting an offer (no model involved)."""

import datetime as dt
import json
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import budget
from app.ai.gateway import (
    LLMResponse,
    credits,
)
from app.api.bookings import place_booking
from app.api.deps import has_module
from app.api.health import ensure_may_book
from app.catalog.importing import phone_key
from app.messaging.whatsapp_ai.base import (
    ACCEPT,
    BUTTON,
    DECLINE,
    HISTORY,
    BotContext,
    Business,
    ToolError,
    _fill,
    _texts,
)
from app.messaging.whatsapp_ai.tools import _bookable, payload_hash

# --- Conversations ------------------------------------------------------------------------------


def _conversation(db: Session, business: Business, phone: str, client_id: UUID, test: bool):
    """The conversation with this number (created on the first message), locked."""
    return (
        db.execute(
            text("""
                INSERT INTO app.whatsapp_conversations
                    (tenant_id, phone, phone_key, client_id, test)
                VALUES (:t, :phone, :key, :client, :test)
                ON CONFLICT (tenant_id, phone_key, test) DO UPDATE
                SET client_id = EXCLUDED.client_id, phone = EXCLUDED.phone
                RETURNING id, messages
            """),
            {
                "t": business.tenant_id,
                "phone": phone[:30],
                "key": phone_key(phone),
                "client": client_id,
                "test": test,
            },
        )
        .mappings()
        .one()
    )


def _recent(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tail of the transcript, starting at a client message (never at a tool result)."""
    if len(messages) <= HISTORY:
        return messages
    tail = messages[-HISTORY:]
    for index, message in enumerate(tail):
        content = message["content"]
        if message["role"] == "user" and not any(
            block.get("type") == "tool_result" for block in content
        ):
            return tail[index:]
    return tail[-1:]


def _record_usage(ctx: BotContext, response: LLMResponse) -> None:
    usage = response.usage
    ctx.db.execute(
        text("""
            INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
            VALUES (:t, 'ai_credits', :quantity, :details, :ref)
        """),
        {
            "t": ctx.business.tenant_id,
            "quantity": credits(response.model, usage),
            "details": json.dumps(
                {
                    "model": response.model,
                    "channel": "whatsapp",
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_read_tokens": usage.cache_read_tokens,
                    "cache_write_tokens": usage.cache_write_tokens,
                }
            ),
            "ref": f"whatsapp_conversation:{ctx.conversation_id}",
        },
    )


def _over_budget(db: Session, business: Business) -> bool:
    month_start = dt.datetime.now(ZoneInfo(business.time_zone)).date().replace(day=1)
    return budget.over_limit(db, month_start)


def _save(db: Session, conversation_id: UUID, messages: list[dict[str, Any]]) -> None:
    db.execute(
        text("""
            UPDATE app.whatsapp_conversations SET messages = :messages, updated_at = now()
            WHERE id = :id
        """),
        {"messages": json.dumps(messages, ensure_ascii=False), "id": conversation_id},
    )


# --- Accepting an offer (no model involved) -------------------------------------------------


def _pending_offer(db: Session, conversation_id: UUID, offer_id: UUID | None):
    return (
        db.execute(
            text("""
                SELECT id, client_id, kind, payload, payload_hash, preview,
                       expires_at < now() AS expired
                FROM app.whatsapp_offers
                WHERE conversation_id = :c AND status = 'pending'
                  AND (CAST(:id AS uuid) IS NULL OR id = :id)
                ORDER BY created_at DESC LIMIT 1 FOR UPDATE
            """),
            {"c": conversation_id, "id": offer_id},
        )
        .mappings()
        .first()
    )


def _decide_offer(
    ctx: BotContext, offer: dict[str, Any], accept: bool, test: bool
) -> tuple[str, dict[str, Any] | None]:
    """Returns the new status and its result."""
    db = ctx.db
    if offer["expired"]:
        return "expired", None
    if not accept:
        return "declined", None
    if not has_module(db, "whatsapp_ai"):
        return "failed", {"error": "module_disabled"}
    if payload_hash(offer["kind"], offer["payload"]) != offer["payload_hash"]:
        return "failed", {"error": "payload_changed"}
    if offer["client_id"] != ctx.client_id:
        return "failed", {"error": "other_client"}
    session_id = UUID(offer["payload"]["session_id"])
    savepoint = db.begin_nested()
    try:
        _bookable(db, ctx.business.tenant_id, session_id)  # still upcoming, not cancelled, a class
        ensure_may_book(db, ctx.business.tenant_id, ctx.client_id)
        requires_plan = db.execute(
            text("SELECT booking_requires_plan FROM app.tenants WHERE id = :id"),
            {"id": ctx.business.tenant_id},
        ).scalar_one()
        booking_id = place_booking(
            db, ctx.business.tenant_id, session_id, ctx.client_id, requires_plan=requires_plan
        )
        booking_status = db.execute(
            text("SELECT status FROM app.bookings WHERE id = :id"), {"id": booking_id}
        ).scalar_one()
    except (ToolError, HTTPException) as error:
        savepoint.rollback()
        detail = error.detail if isinstance(error, HTTPException) else "not_bookable"
        return "failed", {"error": str(detail)}
    if test:  # the business trying the bot: the same checks, nothing booked
        savepoint.rollback()
        return "accepted", {"status": booking_status, "test": True}
    savepoint.commit()
    db.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, on_behalf_of, action, entity_type, entity_id,
                 details)
            VALUES (:t, 'ai', NULL, NULL, 'whatsapp_ai.book_session', 'booking', :booking,
                    :details)
        """),
        {
            "t": ctx.business.tenant_id,
            "booking": booking_id,
            "details": json.dumps(
                {
                    "offer_id": str(offer["id"]),
                    "client_id": str(ctx.client_id),
                    "session_id": str(session_id),
                    "status": booking_status,
                }
            ),
        },
    )
    return "accepted", {"booking_id": str(booking_id), "status": booking_status}


def _answer_offer(ctx: BotContext, offer: dict[str, Any], accept: bool, test: bool) -> str:
    new_status, result = _decide_offer(ctx, offer, accept, test)
    ctx.db.execute(
        text("""
            UPDATE app.whatsapp_offers
            SET status = :status, decided_at = now(), result = :result WHERE id = :id
        """),
        {
            "status": new_status,
            "result": json.dumps(result) if result is not None else None,
            "id": offer["id"],
        },
    )
    texts = _texts(ctx.business.locale)
    if new_status == "accepted":
        key = "waitlisted" if result and result["status"] == "waitlisted" else "booked"
        return _fill(texts[key], **offer["preview"])
    return texts[new_status]


def _decision(body: str) -> tuple[bool, UUID | None] | None:
    """A reply that answers an offer: 1 / 0, or the provider's button with the offer's id."""
    words = body.strip().lower()
    if words in (ACCEPT, DECLINE):
        return words == ACCEPT, None
    button = BUTTON.match(words)
    if button:
        return button.group(1) == "accept", UUID(button.group(2))
    return None
