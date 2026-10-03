"""The AI assistant API: conversations and pending-action confirmation."""

import datetime as dt
import json
from typing import Annotated, Any, Literal
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import actions, assistant
from app.ai.gateway import LLMProvider, get_provider
from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, require
from app.permissions import Permission

router = APIRouter(prefix="/ai", tags=["ai"])

AIDep = Annotated[TenantContext, Depends(require(Permission.AI_USE))]
ProviderDep = Annotated[LLMProvider | None, Depends(get_provider)]


class AIStatus(BaseModel):
    enabled: bool


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
    return AIStatus(enabled=provider is not None)


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
    try:
        assistant.ask(provider, context, user.id, conversation_id, body.text)
    except anthropic.RateLimitError as error:
        raise HTTPException(status_code=429, detail="ai_busy") from error
    except anthropic.APIError as error:
        raise HTTPException(status_code=502, detail="ai_unavailable") from error
    return _load(context.session, conversation_id)


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
