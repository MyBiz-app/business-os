"""CRM: leads and their activity (migration 0028). Needs the CRM module.

Leads are prospective clients, so they use the clients permissions: `clients.read` to see the
pipeline, `clients.write` to change it. Winning a lead ("convert") creates its client record, or
links an existing client with the same email."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import AnonymousSessionDep, TenantContext, has_module, require
from app.permissions import Permission

router = APIRouter(prefix="/leads", tags=["leads"])
public_router = APIRouter(prefix="/public", tags=["public"])

Stage = Literal["new", "contacted", "trial", "offer", "won", "lost"]
STAGES: tuple[Stage, ...] = ("new", "contacted", "trial", "offer", "won", "lost")
LeadSource = Literal[
    "manual", "form", "walk_in", "referral", "instagram", "facebook", "google", "website", "other"
]
ActivityKind = Literal["note", "call", "message", "meeting", "stage", "created", "converted"]


def _crm(permission: Permission):
    def check(context: Annotated[TenantContext, Depends(require(permission))]) -> TenantContext:
        if not has_module(context.session, "crm"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
        return context

    return check


ReadDep = Annotated[TenantContext, Depends(_crm(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(_crm(Permission.CLIENTS_WRITE))]


class LeadFields(BaseModel):
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    interest: str | None = Field(default=None, max_length=2000)
    campaign: str | None = Field(default=None, max_length=100)
    follow_up_on: date | None = None
    owner_user_id: UUID | None = None

    @field_validator(
        "last_name",
        "email",
        "phone",
        "interest",
        "campaign",
        "follow_up_on",
        "owner_user_id",
        mode="before",
    )
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return blank_to_none(value)


class LeadCreate(LeadFields):
    first_name: str = Field(min_length=1, max_length=100)
    source: LeadSource = "manual"

    @field_validator("first_name", mode="before")
    @classmethod
    def strip_first_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LeadUpdate(LeadFields):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    source: LeadSource | None = None


class StageChange(BaseModel):
    stage: Stage
    lost_reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("lost_reason", "note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class ActivityCreate(BaseModel):
    kind: Literal["note", "call", "message", "meeting"]
    note: str = Field(min_length=1, max_length=2000)


class Activity(BaseModel):
    id: UUID
    kind: ActivityKind
    note: str | None
    to_stage: Stage | None
    actor_name: str | None
    occurred_at: datetime


class Lead(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    interest: str | None
    source: LeadSource
    campaign: str | None
    stage: Stage
    lost_reason: str | None
    follow_up_on: date | None
    owner_user_id: UUID | None
    owner_name: str | None
    client_id: UUID | None
    created_at: datetime
    updated_at: datetime
    stage_changed_at: datetime


class LeadDetail(Lead):
    activities: list[Activity]


class StageCount(BaseModel):
    stage: Stage
    count: int


class LeadBoard(BaseModel):
    items: list[Lead]
    counts: list[StageCount]
    new_last_30_days: int
    won_last_30_days: int
    conversion_rate: float | None = Field(
        description="Won ÷ (won + lost) among leads closed in the last 90 days"
    )
    follow_ups_due: int = Field(description="Open leads with a follow-up date today or earlier")


SELECT = """
    SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.interest, l.source, l.campaign,
           l.stage, l.lost_reason, l.follow_up_on, l.owner_user_id,
           coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1)) AS owner_name,
           l.client_id, l.created_at, l.updated_at, l.stage_changed_at
    FROM app.leads l LEFT JOIN app.users u ON u.id = l.owner_user_id
"""


def _like(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _log(
    db: Session,
    tenant_id: UUID,
    lead_id: UUID,
    kind: str,
    note: str | None = None,
    to_stage: str | None = None,
) -> None:
    db.execute(
        text("""
            INSERT INTO app.lead_activities
                (tenant_id, lead_id, kind, note, to_stage, actor_user_id)
            VALUES (:tenant_id, :lead_id, :kind, :note, :to_stage, app.current_user_id())
        """),
        {
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "kind": kind,
            "note": note,
            "to_stage": to_stage,
        },
    )


def _load(db: Session, lead_id: UUID) -> LeadDetail:
    row = db.execute(text(f"{SELECT} WHERE l.id = :id"), {"id": lead_id}).mappings().first()
    if row is None:
        raise not_found()
    activities = db.execute(
        text("""
            SELECT a.id, a.kind, a.note, a.to_stage, a.occurred_at,
                   coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1))
                       AS actor_name
            FROM app.lead_activities a LEFT JOIN app.users u ON u.id = a.actor_user_id
            WHERE a.lead_id = :id ORDER BY a.occurred_at DESC, a.id
        """),
        {"id": lead_id},
    ).mappings()
    return LeadDetail(
        **dict(row), activities=[Activity.model_validate(dict(a)) for a in activities]
    )


def _check_owner(db: Session, owner_user_id: UUID | None) -> None:
    if owner_user_id is None:
        return
    member = db.execute(
        text("SELECT 1 FROM app.tenant_members WHERE user_id = :id"), {"id": owner_user_id}
    ).scalar()
    if member is None:
        raise HTTPException(status_code=422, detail="unknown_owner")


@router.get("")
def list_leads(
    context: ReadDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    source: LeadSource | None = None,
    owner_user_id: UUID | None = None,
    closed_days: Annotated[
        int, Query(ge=0, le=365, description="Won / lost leads closed in this many days")
    ] = 30,
) -> LeadBoard:
    """The pipeline: open leads, plus won and lost ones closed recently."""
    db = context.session
    where = """WHERE (l.stage NOT IN ('won', 'lost')
                      OR l.stage_changed_at > now() - make_interval(days => :closed_days))"""
    params: dict[str, object] = {"closed_days": closed_days}
    if search and search.strip():
        where += " AND concat_ws(' ', l.first_name, l.last_name, l.email, l.phone, l.interest)"
        where += " ILIKE :pattern"
        params["pattern"] = _like(search.strip())
    if source:
        where += " AND l.source = :source"
        params["source"] = source
    if owner_user_id:
        where += " AND l.owner_user_id = :owner"
        params["owner"] = owner_user_id
    rows = db.execute(
        text(f"""
            {SELECT} {where}
            ORDER BY l.follow_up_on NULLS LAST, l.stage_changed_at DESC LIMIT 500
        """),
        params,
    ).mappings()
    items = [Lead.model_validate(dict(r)) for r in rows]
    stats = db.execute(
        text("""
            SELECT
              count(*) FILTER (WHERE created_at > now() - interval '30 days') AS new_30,
              count(*) FILTER (WHERE stage = 'won'
                               AND stage_changed_at > now() - interval '30 days') AS won_30,
              count(*) FILTER (WHERE stage = 'won'
                               AND stage_changed_at > now() - interval '90 days') AS won_90,
              count(*) FILTER (WHERE stage = 'lost'
                               AND stage_changed_at > now() - interval '90 days') AS lost_90,
              count(*) FILTER (
                  WHERE stage NOT IN ('won', 'lost') AND follow_up_on <= (
                      SELECT (now() AT TIME ZONE t.time_zone)::date FROM app.tenants t
                      WHERE t.id = app.current_tenant_id())) AS due
            FROM app.leads
        """)
    ).one()
    counts = {stage: 0 for stage in STAGES}
    for lead in items:
        counts[lead.stage] += 1
    closed = stats.won_90 + stats.lost_90
    return LeadBoard(
        items=items,
        counts=[StageCount(stage=s, count=c) for s, c in counts.items()],
        new_last_30_days=stats.new_30,
        won_last_30_days=stats.won_30,
        conversion_rate=round(stats.won_90 / closed, 3) if closed else None,
        follow_ups_due=stats.due,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_lead(body: LeadCreate, context: WriteDep) -> LeadDetail:
    db = context.session
    _check_owner(db, body.owner_user_id)
    lead_id = db.execute(
        text("""
            INSERT INTO app.leads
                (tenant_id, first_name, last_name, email, phone, interest, source, campaign,
                 follow_up_on, owner_user_id)
            VALUES (:tenant_id, :first_name, :last_name, lower(:email), :phone, :interest,
                    :source, :campaign, :follow_up_on, :owner_user_id)
            RETURNING id
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id},
    ).scalar_one()
    _log(db, context.tenant_id, lead_id, "created", to_stage="new")
    return _load(db, lead_id)


class LeadOwner(BaseModel):
    user_id: UUID
    name: str


@router.get("/owners")
def lead_owners(context: ReadDep) -> list[LeadOwner]:
    """Team members a lead can be assigned to."""
    rows = context.session.execute(
        text("""
            SELECT m.user_id,
                   coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1)) AS name
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id ORDER BY 2
        """)
    ).mappings()
    return [LeadOwner.model_validate(dict(r)) for r in rows]


@router.get("/{lead_id}")
def get_lead(lead_id: UUID, context: ReadDep) -> LeadDetail:
    return _load(context.session, lead_id)


@router.patch("/{lead_id}")
def update_lead(lead_id: UUID, body: LeadUpdate, context: WriteDep) -> LeadDetail:
    db = context.session
    changes = body.model_dump(exclude_unset=True)
    for required in ("first_name", "source"):
        if required in changes and changes[required] is None:
            del changes[required]
    if "owner_user_id" in changes:
        _check_owner(db, changes["owner_user_id"])
    if changes.get("email"):
        changes["email"] = changes["email"].lower()
    if changes:
        updated = db.execute(
            text(f"UPDATE app.leads SET {set_clause(changes)} WHERE id = :id RETURNING id"),
            {**changes, "id": lead_id},
        ).scalar()
        if updated is None:
            raise not_found()
    return _load(db, lead_id)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: UUID, context: WriteDep) -> None:
    deleted = context.session.execute(
        text("DELETE FROM app.leads WHERE id = :id RETURNING id"), {"id": lead_id}
    ).scalar()
    if deleted is None:
        raise not_found()


@router.post("/{lead_id}/stage")
def change_stage(lead_id: UUID, body: StageChange, context: WriteDep) -> LeadDetail:
    """Moves the lead to another stage. "won" is reached by converting it to a client."""
    db = context.session
    current = db.execute(
        text("SELECT stage, client_id FROM app.leads WHERE id = :id FOR UPDATE"), {"id": lead_id}
    ).first()
    if current is None:
        raise not_found()
    if body.stage == "won" and current.client_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="convert_to_win")
    if body.stage != current.stage:
        db.execute(
            text("""
                UPDATE app.leads
                SET stage = :stage, stage_changed_at = now(), updated_at = now(),
                    lost_reason = CASE WHEN :stage = 'lost' THEN :reason END
                WHERE id = :id
            """),
            {"stage": body.stage, "reason": body.lost_reason, "id": lead_id},
        )
        _log(db, context.tenant_id, lead_id, "stage", body.note or body.lost_reason, body.stage)
    return _load(db, lead_id)


@router.post("/{lead_id}/activities", status_code=status.HTTP_201_CREATED)
def add_activity(lead_id: UUID, body: ActivityCreate, context: WriteDep) -> LeadDetail:
    db = context.session
    exists = db.execute(text("SELECT 1 FROM app.leads WHERE id = :id"), {"id": lead_id}).scalar()
    if exists is None:
        raise not_found()
    _log(db, context.tenant_id, lead_id, body.kind, body.note.strip())
    db.execute(text("UPDATE app.leads SET updated_at = now() WHERE id = :id"), {"id": lead_id})
    return _load(db, lead_id)


@router.post("/{lead_id}/convert")
def convert_lead(lead_id: UUID, context: WriteDep) -> LeadDetail:
    """Wins the lead: links the client with the same email, or creates the client."""
    db = context.session
    lead = (
        db.execute(text("SELECT * FROM app.leads WHERE id = :id FOR UPDATE"), {"id": lead_id})
        .mappings()
        .first()
    )
    if lead is None:
        raise not_found()
    client_id = lead["client_id"]
    if client_id is None and lead["email"]:
        client_id = db.execute(
            text("""
                SELECT id FROM app.clients
                WHERE lower(email) = lower(:email) AND erased_at IS NULL
            """),
            {"email": lead["email"]},
        ).scalar()
        if client_id is not None:
            db.execute(
                text("""
                    UPDATE app.clients SET status = 'active', updated_at = now()
                    WHERE id = :id AND status = 'lead'
                """),
                {"id": client_id},
            )
    if client_id is None:
        # Lead sources map onto client sources; the inquiry form counts as the website.
        source = {"manual": None, "form": "website"}.get(lead["source"], lead["source"])
        client_id = db.execute(
            text("""
                INSERT INTO app.clients
                    (tenant_id, first_name, last_name, email, phone, notes, status, source)
                VALUES (:tenant_id, :first_name, :last_name, :email, :phone, :notes, 'active',
                        :source)
                RETURNING id
            """),
            {
                "tenant_id": context.tenant_id,
                "first_name": lead["first_name"],
                "last_name": lead["last_name"],
                "email": lead["email"],
                "phone": lead["phone"],
                "notes": lead["interest"],
                "source": source,
            },
        ).scalar_one()
    db.execute(
        text("""
            UPDATE app.leads
            SET client_id = :client_id, stage = 'won', stage_changed_at = now(),
                updated_at = now(), lost_reason = NULL
            WHERE id = :id
        """),
        {"client_id": client_id, "id": lead_id},
    )
    _log(db, context.tenant_id, lead_id, "converted", to_stage="won")
    return _load(db, lead_id)


# --- Public inquiry form ----------------------------------------------------------------------


class InquiryCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    interest: str | None = Field(default=None, max_length=2000)
    # A field people never see: bots that fill every input fill it too.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("first_name", "last_name", "email", "phone", "interest", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


@public_router.post("/businesses/{code}/inquiries", status_code=status.HTTP_202_ACCEPTED)
def submit_inquiry(code: str, body: InquiryCreate, db: AnonymousSessionDep) -> None:
    """Someone interested leaves their details; the business sees them as a new lead."""
    if body.email is None and body.phone is None:
        raise HTTPException(status_code=422, detail="email_or_phone_required")
    if body.website:
        return  # a bot: accept quietly, store nothing
    try:
        with db.begin_nested():
            db.execute(
                text("""
                    SELECT app.submit_lead(
                        :code, :first_name, :last_name, :email, :phone, :interest)
                """),
                {"code": code, **body.model_dump(exclude={"website"})},
            )
    except DBAPIError as error:
        code_ = getattr(error.orig, "sqlstate", None)
        if code_ == "P0001":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too_many_requests"
            ) from error
        if code_ == "P0002":
            raise not_found() from error
        raise
