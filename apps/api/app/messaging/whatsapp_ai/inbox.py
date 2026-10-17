"""The answer-whatsapp job."""

import json
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.ai import budget
from app.ai.gateway import (
    LLMProvider,
    get_provider,
)
from app.api.deps import has_module
from app.core.db import open_session
from app.messaging.whatsapp_ai.base import Reply
from app.messaging.whatsapp_ai.handle import handle
from app.providers.choice import choose

# --- The answer-whatsapp job ---------------------------------------------------------------------

INBOX_ATTEMPTS = 3
INBOX_BATCH = 100


def _queue_reply(db: Session, tenant_id: UUID, phone: str, reply: Reply) -> None:
    """The reply goes out like any message: through the business's provider (the simulated one
    marks it sent at once), logged and counted as usage."""
    chosen = choose(db, tenant_id, "messaging")
    simulated = chosen.instance.simulated
    db.execute(
        text("""
            INSERT INTO app.messages
                (tenant_id, client_id, channel, to_phone, body, status, simulated, provider,
                 sent_at)
            VALUES (:t, :client, 'whatsapp', :phone, :body, :status, :simulated, :provider,
                    CASE WHEN :simulated THEN now() END)
        """),
        {
            "t": tenant_id,
            "client": reply.client_id,
            "phone": phone[:30],
            "body": reply.text,
            "status": "sent" if simulated else "queued",
            "simulated": simulated,
            "provider": chosen.info.name,
        },
    )
    db.execute(
        text("""
            INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
            VALUES (:t, 'messages', 1, :details, 'whatsapp_ai')
        """),
        {"t": tenant_id, "details": json.dumps({"channel": "whatsapp", "simulated": simulated})},
    )


def _mark(db: Session | Connection, inbox_id: int, status: str, note: str | None = None) -> None:
    db.execute(
        text("""
            UPDATE app.whatsapp_inbox
            SET status = :status, note = :note, attempts = attempts + 1, handled_at = now()
            WHERE id = :id
        """),
        {"status": status, "note": note, "id": inbox_id},
    )


def _answer_one(db: Session, inbox_id: int, provider: LLMProvider) -> str:
    row = db.execute(
        text("""
            SELECT tenant_id, from_phone, body FROM app.whatsapp_inbox
            WHERE id = :id AND status = 'received' FOR UPDATE SKIP LOCKED
        """),
        {"id": inbox_id},
    ).first()
    if row is None:
        return "gone"  # another run has it
    if not has_module(db, "whatsapp_ai"):
        _mark(db, inbox_id, "skipped", "module_disabled")
        return "skipped"
    if budget.platform_paused(db):  # MyBiz stopped AI for this business, or for everyone
        _mark(db, inbox_id, "skipped", "ai_paused")
        return "skipped"
    reply = handle(db, row.tenant_id, row.from_phone, row.body, provider)
    if reply is None:
        _mark(db, inbox_id, "skipped", "unknown_number")
        return "skipped"
    _queue_reply(db, row.tenant_id, row.from_phone, reply)
    _mark(db, inbox_id, "answered")
    return "answered"


def answer_inbox(conn: Connection, provider: LLMProvider | None = None) -> dict[str, int]:
    """Answers the clients' WhatsApp messages waiting in the inbox, oldest first. Each one is
    handled in its own transaction inside its business (row-level security applies), acting as
    the AI on behalf of the owner who turned the module on; the audit log records the AI as
    the actor of any booking. Without an AI provider (or in demo mode) the messages wait."""
    provider = provider if provider is not None else get_provider()
    if getattr(provider, "model", None) == "demo":
        provider = None  # the demo answers only the assistant's scripted questions
    rows = conn.execute(
        text("""
            SELECT i.id, i.tenant_id, i.attempts,
                   (SELECT m.user_id FROM app.tenant_members m
                    WHERE m.tenant_id = i.tenant_id AND m.role = 'owner'
                    ORDER BY m.created_at LIMIT 1) AS owner_id
            FROM app.whatsapp_inbox i
            WHERE i.status = 'received' AND i.attempts < :max
            ORDER BY i.received_at LIMIT :batch
        """),
        {"max": INBOX_ATTEMPTS, "batch": INBOX_BATCH},
    ).all()
    counts = {"answered": 0, "skipped": 0, "failed": 0, "waiting": 0}
    if provider is None:
        counts["waiting"] = len(rows)
        return counts
    for row in rows:
        if row.owner_id is None:
            _mark(conn, row.id, "skipped", "no_owner")
            counts["skipped"] += 1
            continue
        db = open_session(conn.engine, row.owner_id, row.tenant_id)
        try:
            outcome = _answer_one(db, row.id, provider)
            db.commit()
        except Exception as error:  # the AI is busy or down: try again on the next run
            db.rollback()
            last = row.attempts + 1 >= INBOX_ATTEMPTS
            conn.execute(
                text("""
                    UPDATE app.whatsapp_inbox
                    SET attempts = attempts + 1, note = :note,
                        status = CASE WHEN :last THEN 'failed' ELSE status END
                    WHERE id = :id
                """),
                {"note": f"{type(error).__name__}: {error}"[:500], "last": last, "id": row.id},
            )
            outcome = "failed" if last else "waiting"
        finally:
            db.close()
        if outcome != "gone":
            counts[outcome] += 1
    return counts
