"""The post drafts Shira (the content agent) prepares, for the owner to look at (migration 0096).

Publishing goes through the AI confirmation card, never from here."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.common import not_found
from app.api.social import ManageDep, ReadDep

router = APIRouter(prefix="/social/drafts", tags=["social"])


class SocialDraft(BaseModel):
    id: UUID
    network: str | None
    body: str
    image_url: str | None
    idea: str | None
    created_at: datetime


@router.get("")
def list_social_drafts(context: ReadDep) -> list[SocialDraft]:
    """The open drafts, newest first."""
    rows = context.session.execute(
        text("""
            SELECT id, network, body, image_url, idea, created_at
            FROM app.social_drafts WHERE status = 'draft'
            ORDER BY created_at DESC LIMIT 50
        """)
    ).mappings()
    return [SocialDraft.model_validate(dict(r)) for r in rows]


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_social_draft(draft_id: UUID, context: ManageDep) -> None:
    done = context.session.execute(
        text(
            "UPDATE app.social_drafts SET status = 'discarded' WHERE id = :id AND status = 'draft'"
        ),
        {"id": draft_id},
    )
    if done.rowcount == 0:
        raise not_found()
