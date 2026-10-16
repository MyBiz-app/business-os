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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import actions, assistant, budget
from app.ai.agents import CATALOG, HANDOFF_CHARS, find_agent, member_role_keys, state_of
from app.ai.gateway import LLMProvider, ProviderBusy, ProviderUnavailable, get_provider
from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, ensure_branch_allowed, has_module, require
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


class AgentSuggestion(BaseModel):
    """A card offering to hand the user over to a specialist agent."""

    agent_key: str
    reason: str


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    pending_actions: list[PendingAction] = []
    suggestions: list[AgentSuggestion] = []


class Conversation(BaseModel):
    id: UUID
    agent_key: str
    title: str | None
    page_context: str | None
    location_ids: list[UUID] | None = Field(
        description="The branches this chat was narrowed to (none: not narrowed)"
    )
    turns: list[Turn]
    updated_at: dt.datetime


class ConversationSummary(BaseModel):
    id: UUID
    agent_key: str
    title: str
    archived: bool
    updated_at: dt.datetime


class ConversationStart(BaseModel):
    agent_key: str = Field(default="chief", description="A built-in key or custom:<id>")
    location_ids: list[UUID] | None = Field(
        default=None, description="Narrow the chat to these branches (within the user's own)"
    )
    page_context: str | None = Field(
        default=None, max_length=200, description="The screen the chat is opened from"
    )
    handoff_from: UUID | None = Field(
        default=None, description="A conversation of this user whose last exchange is carried over"
    )


def _user_text(message: dict[str, Any]) -> str | None:
    """The user's own words (the last text block; the first is the context block)."""
    content = message["content"]
    if isinstance(content, str):
        return content
    texts = [b["text"] for b in content if b.get("type") == "text"]
    if not texts or any(b.get("type") == "tool_result" for b in content):
        return None
    return texts[-1] if not texts[-1].startswith("<context>") else None


def _suggestions(message: dict[str, Any]) -> list[AgentSuggestion]:
    found = []
    for block in message["content"] if isinstance(message["content"], list) else []:
        if block.get("type") != "tool_result" or block.get("is_error"):
            continue
        try:
            result = json.loads(block["content"])
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and "agent_suggestion" in result:
            found.append(AgentSuggestion.model_validate(result["agent_suggestion"]))
    return found


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
            text("""
                SELECT id, messages, updated_at, agent_key, title, page_context, scope
                FROM app.ai_conversations WHERE id = :id
            """),
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
            for suggestion in _suggestions(message):
                if not turns or turns[-1].role != "assistant":
                    turns.append(Turn(role="assistant", text=""))
                turns[-1].suggestions.append(suggestion)
        else:
            words = "\n\n".join(
                b["text"] for b in message["content"] if b.get("type") == "text"
            ).strip()
            if turns and turns[-1].role == "assistant":
                turns[-1].text = "\n\n".join(t for t in (turns[-1].text, words) if t)
            else:
                turns.append(Turn(role="assistant", text=words))
    scope = row["scope"] or {}
    return Conversation(
        id=row["id"],
        agent_key=row["agent_key"],
        title=row["title"],
        page_context=row["page_context"],
        location_ids=scope.get("location_ids"),
        turns=turns,
        updated_at=row["updated_at"],
    )


@router.get("/status")
def ai_status(_context: AIDep, provider: ProviderDep) -> AIStatus:
    return AIStatus(enabled=provider is not None, demo=getattr(provider, "model", None) == "demo")


@router.get("/conversations")
def list_conversations(
    context: AIDep,
    agent: Annotated[str | None, Query(description="Only chats with this agent")] = None,
    archived: Annotated[bool, Query(description="Archived chats instead of the live ones")] = False,
) -> list[ConversationSummary]:
    rows = context.session.execute(
        text("""
            SELECT id, agent_key, updated_at, archived_at IS NOT NULL AS archived,
                   coalesce(title, messages -> 0 -> 'content' -> -1 ->> 'text', '') AS title
            FROM app.ai_conversations
            WHERE (archived_at IS NOT NULL) = :archived
              AND (CAST(:agent AS text) IS NULL OR agent_key = :agent)
            ORDER BY updated_at DESC LIMIT 20
        """),
        {"archived": archived, "agent": agent},
    ).mappings()
    return [
        ConversationSummary(
            id=r["id"],
            agent_key=r["agent_key"],
            title=r["title"][:80],
            archived=r["archived"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def ensure_agent_usable(context: TenantContext, agent_key: str) -> None:
    """The agent exists for this business and this user may talk to it now."""
    db = context.session
    locale = db.execute(
        text("SELECT locale FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar()
    agent = find_agent(db, agent_key, locale or "en")
    if agent is None:
        raise not_found()
    state, _upsell = state_of(db, agent, member_role_keys(db, context.role))
    if state != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"agent_{state}")


def _handoff_summary(db: Session, conversation_id: UUID) -> str:
    """The last question and answer of a conversation, short enough to hand to the next agent."""
    source = _load(db, conversation_id)
    asked = next((t.text for t in reversed(source.turns) if t.role == "user"), "")
    answered = next((t.text for t in reversed(source.turns) if t.role == "assistant"), "")
    return f"The user asked: {asked[:300]} The previous answer: {answered[:HANDOFF_CHARS]}"


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    context: AIDep, user: UserDep, body: ConversationStart | None = None
) -> Conversation:
    body = body or ConversationStart()
    db = context.session
    ensure_agent_usable(context, body.agent_key)
    scope = None
    if body.location_ids is not None:
        known = set(
            db.execute(
                text("SELECT id FROM app.locations WHERE id = ANY(:ids)"),
                {"ids": body.location_ids},
            ).scalars()
        )
        if set(body.location_ids) - known:
            raise HTTPException(status_code=422, detail="unknown_branch")
        for location_id in body.location_ids:
            ensure_branch_allowed(context, location_id)
        scope = json.dumps({"location_ids": [str(i) for i in body.location_ids]})
    handoff = _handoff_summary(db, body.handoff_from) if body.handoff_from else None
    agent_id = db.execute(
        text("SELECT id FROM app.ai_agents WHERE id::text = :raw OR builtin_key = :raw"),
        {"raw": body.agent_key.removeprefix("custom:")},
    ).scalar()
    conversation_id = db.execute(
        text("""
            INSERT INTO app.ai_conversations
                (tenant_id, user_id, agent_id, agent_key, scope, page_context, handoff_summary)
            VALUES (:t, :u, :agent_id, :agent, CAST(:scope AS jsonb), :page, :handoff)
            RETURNING id
        """),
        {
            "t": context.tenant_id,
            "u": user.id,
            "agent_id": agent_id if body.agent_key not in CATALOG else None,
            "agent": body.agent_key,
            "scope": scope,
            "page": body.page_context,
            "handoff": handoff,
        },
    ).scalar_one()
    return _load(db, conversation_id)


@router.post("/conversations/{conversation_id}/archive")
def archive_conversation(conversation_id: UUID, context: AIDep) -> Conversation:
    _load(context.session, conversation_id)
    context.session.execute(
        text("UPDATE app.ai_conversations SET archived_at = now() WHERE id = :id"),
        {"id": conversation_id},
    )
    return _load(context.session, conversation_id)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, context: AIDep) -> Conversation:
    return _load(context.session, conversation_id)


def _month_start(db: Session) -> dt.date:
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return dt.datetime.now(ZoneInfo(time_zone)).date().replace(day=1)


def _check_budget(context: TenantContext, user_id: UUID, provider: LLMProvider) -> None:
    """Soft monthly limit: at the business's limit (its included credits, plus the extra it
    agreed to pay for), new questions wait for next month or a bigger module. A role or a person
    can have a lower limit. Demo answers cost nothing and are never limited."""
    if getattr(provider, "model", None) == "demo":
        return
    db = context.session
    month_start = _month_start(db)
    if budget.over_limit(db, month_start):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_limit_reached")
    if budget.over_person_limit(db, user_id, member_role_keys(db, context.role), month_start):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_user_limit_reached")


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
    chat = _load(context.session, conversation_id)  # 404 unless it is the user's conversation
    ensure_agent_usable(context, chat.agent_key)
    _check_budget(context, user.id, provider)
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
    chat = _load(context.session, conversation_id)
    ensure_agent_usable(context, chat.agent_key)
    _check_budget(context, user.id, provider)
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
