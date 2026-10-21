"""The entry point: one client message in, one reply out."""

import datetime as dt
import json
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.gateway import (
    LLMProvider,
    LLMResponse,
    ProviderBusy,
    ProviderUnavailable,
)
from app.ai.untrusted import prepare
from app.messaging.whatsapp_ai.base import (
    MAX_REPLY,
    MAX_STEPS,
    OFFER_TTL,
    SYSTEM_PROMPT,
    BotContext,
    Reply,
    _business,
    _fill,
    _texts,
    find_client,
)
from app.messaging.whatsapp_ai.conversation import (
    _answer_offer,
    _conversation,
    _decision,
    _over_budget,
    _pending_offer,
    _recent,
    _record_usage,
    _save,
)
from app.messaging.whatsapp_ai.tools import DEFINITIONS, run_tool

# --- The entry point -----------------------------------------------------------------------------


def handle(
    db: Session,
    tenant_id: UUID,
    phone: str,
    body: str,
    provider: LLMProvider,
    *,
    test: bool = False,
) -> Reply | None:
    """Answers one client message. Returns None when the number is not one client's (no answer
    is sent). The caller's session must be inside the business (RLS) and commits."""
    client_id = find_client(db, tenant_id, phone)
    if client_id is None:
        return None
    business = _business(db, tenant_id)
    row = _conversation(db, business, phone, client_id, test)
    ctx = BotContext(db, business, client_id, row["id"])
    messages: list[dict[str, Any]] = list(row["messages"])

    decision = _decision(body)
    if decision is not None:
        offer = _pending_offer(db, ctx.conversation_id, decision[1])
        if offer is not None:
            answer = _answer_offer(ctx, dict(offer), decision[0], test)
            # Kept in the transcript so the model knows what happened on the next message.
            messages.append({"role": "user", "content": [{"type": "text", "text": body}]})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": answer}]})
            _save(db, ctx.conversation_id, messages)
            return Reply(answer, client_id)

    texts = _texts(business.locale)
    if _over_budget(db, business):
        return Reply(texts["unavailable"], client_id)

    now = dt.datetime.now(ZoneInfo(business.time_zone))
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"<context>Today is {now:%A %Y-%m-%d}, local time {now:%H:%M} "
                        f"({business.time_zone}). Business: "
                        f"{json.dumps(business.name, ensure_ascii=False)}.</context>"
                    ),
                },
                {"type": "text", "text": body[:4000]},
            ],
        }
    )
    offer_id: UUID | None = None
    spent: list[LLMResponse] = []
    work = db.begin_nested()
    try:
        for _step in range(MAX_STEPS):
            response = provider.create(
                SYSTEM_PROMPT, prepare(_recent(messages), client_text=True), DEFINITIONS
            )
            spent.append(response)
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in response.content:
                if block.get("type") != "tool_use":
                    continue
                result, is_error = run_tool(ctx, block["name"], block.get("input") or {})
                if not is_error and "offer_id" in result:
                    offer_id = UUID(result["offer_id"])
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                        **({"is_error": True} if is_error else {}),
                    }
                )
            messages.append({"role": "user", "content": results})
        else:
            # Out of steps while still calling tools: close the turn so the history stays valid.
            messages.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "<context>Answer now.</context>"}],
                }
            )
            response = provider.create(
                SYSTEM_PROMPT, prepare(_recent(messages), client_text=True), DEFINITIONS
            )
            spent.append(response)
            messages.append({"role": "assistant", "content": response.content})
    except (ProviderBusy, ProviderUnavailable):
        # Undo the partial turn but keep (and commit) the usage already incurred.
        work.rollback()
        for done in spent:
            _record_usage(ctx, done)
        db.commit()
        raise
    work.commit()

    for done in spent:
        _record_usage(ctx, done)
    # What is sent: the model's last message, plus the server's own line for a new offer
    # (kept in the transcript too, so the conversation shows exactly what the client got).
    final = messages[-1]["content"]
    answer = "\n\n".join(b["text"] for b in final if b.get("type") == "text").strip()
    if offer_id is not None:
        offer = db.execute(
            text("SELECT preview, status FROM app.whatsapp_offers WHERE id = :id"),
            {"id": offer_id},
        ).one()
        if offer.status == "pending":
            line = _fill(
                texts["offer"], minutes=int(OFFER_TTL.total_seconds() // 60), **offer.preview
            )
            final.append({"type": "text", "text": line})
            answer = f"{answer}\n\n{line}" if answer else line
        else:
            offer_id = None
    _save(db, ctx.conversation_id, messages)
    return Reply((answer or texts["unavailable"])[:MAX_REPLY], client_id, offer_id)
