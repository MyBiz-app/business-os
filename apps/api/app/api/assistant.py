"""The AI assistant API: conversations and pending-action confirmation."""

import datetime as dt
import json
import math
import queue
import threading
import time
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import actions, assistant, budget
from app.ai.gateway import LLMProvider, ProviderBusy, ProviderUnavailable, get_provider
from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, has_module, require
from app.core.config import get_settings
from app.core.permissions import Permission
from app.core.rate_limit import MemoryStore

router = APIRouter(prefix="/ai", tags=["ai"])


def require_ai(context: Annotated[TenantContext, Depends(require(Permission.AI_USE))]):
    """The assistant needs an AI module (AI Basic: questions; AI Pro: also actions)."""
    if not has_module(context.session, "ai_basic", "ai_pro"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    return context


AIDep = Annotated[TenantContext, Depends(require_ai)]
ProviderDep = Annotated[LLMProvider | None, Depends(get_provider)]


class AIStatus(BaseModel):
    enabled: bool
    demo: bool = Field(default=False, description="Demo mode: scripted answers, no AI key")


class Question(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class PendingAction(BaseModel):
    id: UUID
    tool_name: str
    preview: dict[str, Any]
    status: Literal["pending", "rejected", "expired", "executed", "failed"]
    expires_at: dt.datetime
    result: dict[str, Any] | None


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    pending_actions: list[PendingAction] = []


class Conversation(BaseModel):
    id: UUID
    turns: list[Turn]
    updated_at: dt.datetime


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    updated_at: dt.datetime


def _user_text(message: dict[str, Any]) -> str | None:
    """The user's own words (the last text block; the first is the context block)."""
    content = message["content"]
    if isinstance(content, str):
        return content
    texts = [b["text"] for b in content if b.get("type") == "text"]
    if not texts or any(b.get("type") == "tool_result" for b in content):
        return None
    return texts[-1] if not texts[-1].startswith("<context>") else None


def _proposed_actions(message: dict[str, Any]) -> list[str]:
    ids = []
    for block in message["content"] if isinstance(message["content"], list) else []:
        if block.get("type") != "tool_result" or block.get("is_error"):
            continue
        try:
            result = json.loads(block["content"])
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and "pending_action_id" in result:
            ids.append(result["pending_action_id"])
    return ids


def _load(db: Session, conversation_id: UUID) -> Conversation:
    row = (
        db.execute(
            text("SELECT id, messages, updated_at FROM app.ai_conversations WHERE id = :id"),
            {"id": conversation_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    pending = {
        str(r["id"]): PendingAction.model_validate(dict(r))
        for r in db.execute(
            text("""
                SELECT id, tool_name, preview, status, expires_at, result
                FROM app.pending_actions WHERE conversation_id = :id ORDER BY created_at
            """),
            {"id": conversation_id},
        ).mappings()
    }

    turns: list[Turn] = []
    for message in row["messages"]:
        if message["role"] == "user":
            words = _user_text(message)
            if words is not None:
                turns.append(Turn(role="user", text=words))
            # Tool results that created a pending action attach its card to the answer.
            for action_id in _proposed_actions(message):
                if action_id in pending:
                    if not turns or turns[-1].role != "assistant":
                        turns.append(Turn(role="assistant", text=""))
                    turns[-1].pending_actions.append(pending[action_id])
        else:
            words = "\n\n".join(
                b["text"] for b in message["content"] if b.get("type") == "text"
            ).strip()
            if turns and turns[-1].role == "assistant":
                turns[-1].text = "\n\n".join(t for t in (turns[-1].text, words) if t)
            else:
                turns.append(Turn(role="assistant", text=words))
    return Conversation(id=row["id"], turns=turns, updated_at=row["updated_at"])


@router.get("/status")
def ai_status(_context: AIDep, provider: ProviderDep) -> AIStatus:
    return AIStatus(enabled=provider is not None, demo=getattr(provider, "model", None) == "demo")


@router.get("/conversations")
def list_conversations(context: AIDep) -> list[ConversationSummary]:
    rows = context.session.execute(
        text("""
            SELECT id, updated_at,
                   coalesce(messages -> 0 -> 'content' -> -1 ->> 'text', '') AS title
            FROM app.ai_conversations ORDER BY updated_at DESC LIMIT 20
        """)
    ).mappings()
    return [
        ConversationSummary(id=r["id"], title=r["title"][:80], updated_at=r["updated_at"])
        for r in rows
    ]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(context: AIDep, user: UserDep) -> Conversation:
    conversation_id = context.session.execute(
        text("""
            INSERT INTO app.ai_conversations (tenant_id, user_id) VALUES (:t, :u) RETURNING id
        """),
        {"t": context.tenant_id, "u": user.id},
    ).scalar_one()
    return _load(context.session, conversation_id)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, context: AIDep) -> Conversation:
    return _load(context.session, conversation_id)


def _check_budget(db: Session, provider: LLMProvider) -> None:
    """Soft monthly limit: from 100% of the AI module's allowance, new questions wait for next
    month or a bigger module (demo answers cost nothing and are never limited)."""
    if getattr(provider, "model", None) == "demo":
        return
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    month_start = dt.datetime.now(ZoneInfo(time_zone)).date().replace(day=1)
    if budget.credits_used(db, month_start) >= budget.credits_included(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_limit_reached")


# Concurrent model calls in this worker (a call holds a request thread and a connection).
_model_calls = threading.BoundedSemaphore(get_settings().ai_max_concurrent_calls)

# Counts per API process, like the address limiter (app/core/rate_limit.py).
_user_messages = MemoryStore()


def _check_user_rate(user_id: UUID, provider: LLMProvider) -> None:
    """A per-user ceiling on questions, so one account cannot run up the model bill (P0-6).
    Demo answers cost nothing and are never limited."""
    if getattr(provider, "model", None) == "demo":
        return
    settings = get_settings()
    now = time.time()
    for name, limit, window in (
        ("minute", settings.ai_user_messages_per_minute, 60),
        ("hour", settings.ai_user_messages_per_hour, 3600),
    ):
        if limit <= 0:
            continue
        count, ends = _user_messages.hit(f"ai:{name}:{user_id}", window, now)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="ai_rate_limited",
                headers={"Retry-After": str(max(1, math.ceil(ends - now)))},
            )


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    body: Question,
    context: AIDep,
    user: UserDep,
    provider: ProviderDep,
) -> Conversation:
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ai_not_configured"
        )
    _load(context.session, conversation_id)  # 404 unless it is the user's conversation
    _check_budget(context.session, provider)
    _check_user_rate(user.id, provider)
    if not _model_calls.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ai_busy")
    try:
        assistant.ask(provider, context, user.id, conversation_id, body.text)
    except ProviderBusy as error:
        raise HTTPException(status_code=429, detail="ai_busy") from error
    except ProviderUnavailable as error:
        raise HTTPException(status_code=502, detail="ai_unavailable") from error
    finally:
        _model_calls.release()
    return _load(context.session, conversation_id)


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/conversations/{conversation_id}/messages/stream")
def send_message_stream(
    conversation_id: UUID,
    body: Question,
    context: AIDep,
    user: UserDep,
    provider: ProviderDep,
) -> StreamingResponse:
    """Like `send_message`, but answers as a Server-Sent Events stream: `text` events carry the
    answer as it is written, `done` carries the whole conversation, `error` a failure code."""
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ai_not_configured"
        )
    _load(context.session, conversation_id)
    _check_budget(context.session, provider)
    _check_user_rate(user.id, provider)
    if not _model_calls.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ai_busy")

    events: queue.Queue[tuple[str, Any] | None] = queue.Queue()

    def work() -> None:
        try:
            assistant.ask(
                provider,
                context,
                user.id,
                conversation_id,
                body.text,
                on_text=lambda chunk: events.put(("text", {"text": chunk})),
            )
            context.session.commit()  # the client may read the conversation right after `done`
            events.put(("done", _load(context.session, conversation_id).model_dump(mode="json")))
        except ProviderBusy:
            events.put(("error", {"detail": "ai_busy"}))
        except ProviderUnavailable:
            events.put(("error", {"detail": "ai_unavailable"}))
        finally:
            _model_calls.release()
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.post("/pending-actions/{action_id}/confirm")
def confirm_action(action_id: UUID, context: AIDep, user: UserDep) -> PendingAction:
    actions.decide(context, user.id, action_id, confirm=True)
    return _pending(context.session, action_id)


@router.post("/pending-actions/{action_id}/reject")
def reject_action(action_id: UUID, context: AIDep, user: UserDep) -> PendingAction:
    actions.decide(context, user.id, action_id, confirm=False)
    return _pending(context.session, action_id)


def _pending(db: Session, action_id: UUID) -> PendingAction:
    row = (
        db.execute(
            text("""
                SELECT id, tool_name, preview, status, expires_at, result
                FROM app.pending_actions WHERE id = :id
            """),
            {"id": action_id},
        )
        .mappings()
        .one()
    )
    return PendingAction.model_validate(dict(row))
