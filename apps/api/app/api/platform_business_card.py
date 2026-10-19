"""The business 360 card in the MyBiz console (K2): a timeline, internal notes, tags, the MyBiz
team member who looks after the business, and the trials that end soon.

Reading needs `businesses.read`; writing a note or the card needs `businesses.act`. The timeline
leaves out the parts the caller may not read (invoices need `billing.manage`, requests need
`inbox.manage`). Notes are internal and never shown to the business. The rules live in database
functions (migration 0146), which check the same permissions."""

import datetime as dt
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.platform import ActDep, AdminDep, run_rule

router = APIRouter(prefix="/platform", tags=["platform"])


class BusinessCard(BaseModel):
    tags: list[str]
    account_owner: str | None = Field(description="The MyBiz team member who looks after it")
    updated_by: str | None
    updated_at: dt.datetime | None
    trial_ends_at: dt.datetime
    closed_at: dt.datetime | None


class CardChange(BaseModel):
    tags: list[str] = Field(max_length=12)
    account_owner: str | None = Field(default=None, max_length=254)


class BusinessNote(BaseModel):
    id: UUID
    author_email: str
    body: str
    created_at: dt.datetime


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class TimelineEvent(BaseModel):
    at: dt.datetime
    kind: str = Field(
        description="signup, trial_ends, closed, invoice, request, change or note; "
        "the details depend on the kind"
    )
    actor: str | None
    details: dict[str, Any]


class TrialEnding(BaseModel):
    tenant_id: UUID
    name: str
    owner_email: str | None
    trial_ends_at: dt.datetime
    active_clients: int
    has_card: bool
    account_owner: str | None


def read_card(db: AdminDep, tenant_id: UUID) -> BusinessCard:
    """The card through `run_rule`, so an unknown business is a 404 and a missing right a 403."""
    row = run_rule(db, "SELECT to_jsonb(c) FROM app.platform_business_card(:t) c", {"t": tenant_id})
    return BusinessCard.model_validate(row)


@router.get("/businesses/{tenant_id}/card")
def business_card(tenant_id: UUID, db: AdminDep) -> BusinessCard:
    """Tags, the account owner and the trial end of one business."""
    return read_card(db, tenant_id)


@router.put("/businesses/{tenant_id}/card")
def set_business_card(tenant_id: UUID, body: CardChange, db: ActDep) -> BusinessCard:
    """Replaces the tags and the account owner (an email of the MyBiz team, or empty)."""
    run_rule(
        db,
        "SELECT app.platform_business_card_set(:t, CAST(:tags AS text[]), :owner)",
        {"t": tenant_id, "tags": body.tags, "owner": body.account_owner},
    )
    return read_card(db, tenant_id)


def read_notes(db: AdminDep, tenant_id: UUID) -> list[BusinessNote]:
    rows = run_rule(
        db,
        "SELECT coalesce(jsonb_agg(to_jsonb(n) ORDER BY n.created_at DESC), '[]'::jsonb) "
        "FROM app.platform_business_notes(:t) n",
        {"t": tenant_id},
    )
    return [BusinessNote.model_validate(row) for row in rows]


@router.get("/businesses/{tenant_id}/notes")
def business_notes(tenant_id: UUID, db: AdminDep) -> list[BusinessNote]:
    """Internal notes, newest first (the last 200)."""
    return read_notes(db, tenant_id)


@router.post("/businesses/{tenant_id}/notes", status_code=201)
def add_business_note(tenant_id: UUID, body: NoteIn, db: ActDep) -> list[BusinessNote]:
    """Writes an internal note about a business; returns the notes."""
    run_rule(
        db,
        "SELECT app.platform_business_note_add(:t, :body)",
        {"t": tenant_id, "body": body.body},
    )
    return read_notes(db, tenant_id)


@router.get("/businesses/{tenant_id}/timeline")
def business_timeline(tenant_id: UUID, db: AdminDep) -> list[TimelineEvent]:
    """Sign-up, trial, invoices, requests, changes by the team and notes, newest first (150)."""
    rows = run_rule(
        db,
        "SELECT coalesce(jsonb_agg(to_jsonb(e) ORDER BY e.at DESC), '[]'::jsonb) "
        "FROM app.platform_business_timeline(:t) e",
        {"t": tenant_id},
    )
    return [TimelineEvent.model_validate(row) for row in rows]


@router.get("/trials-ending")
def trials_ending(
    db: AdminDep,
    days: Annotated[int, Query(ge=1, le=30, description="Look ahead this many days")] = 7,
) -> list[TrialEnding]:
    """Businesses whose free trial ends within `days` or ended in the last three days
    (at most 200), soonest first."""
    rows = db.execute(
        text("SELECT * FROM app.platform_trials_ending(:days)"), {"days": days}
    ).mappings()
    return [TrialEnding.model_validate(dict(row)) for row in rows]
