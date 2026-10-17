import json
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, ensure_not_erased, not_found, set_clause
from app.api.deps import TenantContext, ensure_branch_allowed, ensure_branch_visible, require
from app.api.pagination import PageDep
from app.catalog.verticals import VERTICAL_PACKS, VerticalPack, clean_client_fields
from app.core import events
from app.core.permissions import Permission
from app.messaging.consent import request_origin

router = APIRouter(prefix="/clients", tags=["clients"])

ClientStatus = Literal["active", "inactive", "lead"]
ClientSource = Literal[
    "walk_in", "referral", "instagram", "facebook", "google", "website", "app", "other"
]

ConsentSource = Literal[
    "app_join",
    "app_profile",
    "desk_signed",
    "desk_verbal",
    "desk_other",
    "unsubscribe_link",
    "unsubscribe_email",
]
DeskConsentSource = Literal["desk_signed", "desk_verbal", "desk_other"]

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

COLUMNS = (
    "id, first_name, last_name, email, phone, date_of_birth, notes, status, source, "
    "custom_fields, home_location_id, created_at, updated_at, erased_at, "
    "marketing_consent_at IS NOT NULL AS marketing_consent, marketing_consent_at, "
    "marketing_consent_source, marketing_opted_out_at, "
    "(email IS NOT NULL AND app.email_is_suppressed(email)) AS email_suppressed"
)


class ClientFields(BaseModel):
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    notes: str | None = Field(default=None, max_length=5000)
    source: ClientSource | None = None
    custom_fields: dict[str, str | int | None] | None = Field(
        default=None,
        description="The vertical pack's extra fields (GET /clients/fields); replaces all",
    )
    home_location_id: UUID | None = Field(
        default=None,
        description="The client's home branch; new clients default to the current branch",
    )

    @field_validator(
        "last_name", "email", "phone", "notes", "date_of_birth", "source", mode="before"
    )
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return blank_to_none(value)


class ClientCreate(ClientFields):
    first_name: str = Field(min_length=1, max_length=100)
    status: ClientStatus = "active"

    @field_validator("first_name")
    @classmethod
    def strip_first_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("first_name must not be blank")
        return value


class ClientUpdate(ClientFields):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: ClientStatus | None = None


class Client(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    date_of_birth: date | None
    notes: str | None
    status: ClientStatus
    source: ClientSource | None
    custom_fields: dict[str, str | int]
    home_location_id: UUID | None
    created_at: datetime
    updated_at: datetime
    erased_at: datetime | None = Field(description="Personal data erased on request (privacy)")
    marketing_consent: bool = Field(
        default=False,
        description="Agreed to marketing messages; service messages are sent either way",
    )
    marketing_consent_at: datetime | None = Field(
        default=None, description="When the agreement was given"
    )
    marketing_consent_source: ConsentSource | None = Field(
        default=None, description="Where the last consent change came from"
    )
    marketing_opted_out_at: datetime | None = Field(
        default=None, description="Stopped ads with the opt-out link; only the client can undo it"
    )
    email_suppressed: bool = Field(
        default=False, description="The address bounced or reported spam: no emails are sent to it"
    )


class ClientListItem(Client):
    """A row of the clients list: the client plus what the list shows at a glance."""

    plan_name: str | None = Field(description="The plan valid today, if any")
    plan_ends_on: date | None
    last_visit: date | None = Field(description="Last check-in, in the business's time zone")


class ClientPage(BaseModel):
    items: list[ClientListItem]
    total: int


def _email_taken(error: IntegrityError) -> HTTPException | None:
    if "clients_tenant_email_key" in str(error.orig):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")
    if "home_location_id" in str(error.orig):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_branch"
        )
    return None


def _join_home_branch(db: Session, client_id: UUID, location_id: UUID | None) -> None:
    """A client's home branch is always on its "my branches" list."""
    if location_id is None:
        return
    db.execute(
        text("""
            INSERT INTO app.client_locations (tenant_id, client_id, location_id)
            VALUES (app.current_tenant_id(), :client, :location) ON CONFLICT DO NOTHING
        """),
        {"client": client_id, "location": location_id},
    )


def _client_row(context: TenantContext, client_id: UUID) -> None:
    home = context.session.execute(
        text("SELECT home_location_id FROM app.clients WHERE id = :id"), {"id": client_id}
    ).first()
    if home is None:
        raise not_found()
    ensure_branch_visible(context, home.home_location_id)


def _pack(db: Session) -> VerticalPack:
    vertical = db.execute(
        text("SELECT vertical FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return VERTICAL_PACKS[vertical]


def _custom_fields(db: Session, values: dict[str, str | int | None] | None) -> str:
    """The values validated against the business's vertical pack, as JSON for the column."""
    try:
        return json.dumps(clean_client_fields(_pack(db), values or {}))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


class ClientFieldDefinition(BaseModel):
    key: str
    kind: Literal["text", "long_text", "number", "date", "select"]
    options: list[str]
    max_length: int


@router.get("/fields")
def client_fields(context: ReadDep) -> list[ClientFieldDefinition]:
    """The extra client fields of the business's vertical (labels come from translations)."""
    return [
        ClientFieldDefinition(
            key=f.key,
            kind=f.kind,
            options=list(f.options),
            max_length=f.max_length,  # type: ignore[arg-type]
        )
        for f in _pack(context.session).client_fields
    ]


# The text the trigram index `clients_search_trgm_idx` covers (migration 0118), word for word.
SEARCH_TEXT = (
    "(coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' || "
    "coalesce(email, '') || ' ' || coalesce(phone, ''))"
)


def _like_pattern(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("")
def list_clients(
    context: ReadDep,
    page_of: PageDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    client_status: Annotated[ClientStatus | None, Query(alias="status")] = None,
    plan: Annotated[
        Literal["valid", "none"] | None,
        Query(description="valid: holds a plan valid today; none: doesn't"),
    ] = None,
    absent_days: Annotated[
        int | None, Query(ge=1, le=365, description="No check-in in this many days")
    ] = None,
) -> ClientPage:
    # RLS limits rows to the current tenant; the filters below narrow further.
    # The current branch's clients, and those without a home branch (they belong to all).
    # In a branch-scoped business a client belongs to the branches on its "my branches" list
    # (see client_locations); one on no list belongs to all.
    where = """WHERE (
        CASE WHEN (SELECT network_scope FROM app.tenants WHERE id = app.current_tenant_id())
                  = 'branch'
             THEN NOT EXISTS (SELECT 1 FROM app.client_locations cl
                              WHERE cl.client_id = app.clients.id)
                  OR EXISTS (SELECT 1 FROM app.client_locations cl
                             WHERE cl.client_id = app.clients.id AND app.in_branch(cl.location_id))
             ELSE home_location_id IS NULL OR app.in_branch(home_location_id)
        END)"""
    params: dict[str, object] = {"limit": page_of.limit, "offset": page_of.offset}
    if search and search.strip():
        # Through the function: row level security would keep Postgres from using the index.
        where += " AND id IN (SELECT app.search_client_ids(:pattern))"
        params["pattern"] = _like_pattern(search.strip())
    if client_status:
        where += " AND status = :status"
        params["status"] = client_status
    if plan:
        # "Today" in the business's time zone, like everywhere plans are checked.
        valid = """EXISTS (
            SELECT 1 FROM app.entitlements e JOIN app.tenants t ON t.id = e.tenant_id
            WHERE e.client_id = app.clients.id AND e.status = 'active'
              AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on
        )"""
        where += f" AND {'' if plan == 'valid' else 'NOT '}{valid}"
    if absent_days:
        where += """ AND NOT EXISTS (
            SELECT 1 FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
            WHERE b.client_id = app.clients.id AND b.status = 'checked_in'
              AND s.starts_at > now() - make_interval(days => :absent_days)
        )"""
        params["absent_days"] = absent_days

    session = context.session
    total = session.execute(text(f"SELECT count(*) FROM app.clients {where}"), params).scalar_one()
    # The page first, then its plans and last visits: two lookups per page, not per client.
    rows = session.execute(
        text(f"""
            WITH page AS (
                SELECT {COLUMNS} FROM app.clients {where}
                ORDER BY first_name, last_name NULLS FIRST, created_at
                LIMIT :limit OFFSET :offset
            ), today AS (
                SELECT (now() AT TIME ZONE time_zone)::date AS day, time_zone
                FROM app.tenants WHERE id = app.current_tenant_id()
            )
            SELECT page.*, plan.name AS plan_name, plan.ends_on AS plan_ends_on,
                   (visit.at AT TIME ZONE today.time_zone)::date AS last_visit
            FROM page CROSS JOIN today
            LEFT JOIN LATERAL (
                SELECT e.name, e.ends_on FROM app.entitlements e
                WHERE e.client_id = page.id AND e.status = 'active'
                  AND today.day BETWEEN e.starts_on AND e.ends_on
                ORDER BY e.ends_on DESC LIMIT 1
            ) plan ON true
            LEFT JOIN LATERAL (
                SELECT max(s.starts_at) AS at FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id
                WHERE b.client_id = page.id AND b.status = 'checked_in'
            ) visit ON true
            ORDER BY page.first_name, page.last_name NULLS FIRST, page.created_at
        """),
        params,
    ).mappings()
    return ClientPage(items=[ClientListItem.model_validate(dict(row)) for row in rows], total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, context: WriteDep) -> Client:
    ensure_branch_allowed(context, body.home_location_id)
    try:
        row = (
            context.session.execute(
                text(f"""
                    INSERT INTO app.clients
                        (tenant_id, first_name, last_name, email, phone, date_of_birth, notes,
                         status, source, custom_fields, home_location_id)
                    VALUES
                        (:tenant_id, :first_name, :last_name, :email, :phone, :date_of_birth,
                         :notes, :status, :source, CAST(:custom_fields AS jsonb),
                         :home_location_id)
                    RETURNING {COLUMNS}
                """),
                {
                    **body.model_dump(),
                    "custom_fields": _custom_fields(context.session, body.custom_fields),
                    "tenant_id": context.tenant_id,
                },
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:
        raise _email_taken(error) or error from error
    _join_home_branch(context.session, row["id"], row["home_location_id"])
    events.record(context.session, "first_client", once=True)
    return Client.model_validate(dict(row))


@router.get("/{client_id}/branches")
def client_branches(client_id: UUID, context: ReadDep) -> list[UUID]:
    """The branches on the client's "my branches" list."""
    _client_row(context, client_id)
    return list(
        context.session.execute(
            text(
                "SELECT location_id FROM app.client_locations WHERE client_id = :id"
                " ORDER BY created_at, location_id"
            ),
            {"id": client_id},
        ).scalars()
    )


class ClientBranches(BaseModel):
    location_ids: list[UUID] = Field(max_length=100)


@router.put("/{client_id}/branches")
def set_client_branches(client_id: UUID, body: ClientBranches, context: WriteDep) -> list[UUID]:
    """Replaces the client's "my branches" list. A member kept to some branches may only
    change the list within them."""
    _client_row(context, client_id)
    wanted = set(body.location_ids)
    known = context.session.execute(
        text("SELECT count(*) FROM app.locations WHERE id = ANY(:ids)"), {"ids": list(wanted)}
    ).scalar_one()
    if known != len(wanted):
        raise HTTPException(status_code=422, detail="unknown_branch")
    for location_id in wanted:
        ensure_branch_allowed(context, location_id)
    context.session.execute(
        text("DELETE FROM app.client_locations WHERE client_id = :id AND location_id <> ALL(:ids)"),
        {"id": client_id, "ids": list(wanted)},
    )
    for location_id in wanted:
        _join_home_branch(context.session, client_id, location_id)
    return client_branches(client_id, context)


@router.get("/{client_id}")
def get_client(client_id: UUID, context: ReadDep) -> Client:
    row = (
        context.session.execute(
            text(f"SELECT {COLUMNS} FROM app.clients WHERE id = :id"), {"id": client_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row["home_location_id"])
    return Client.model_validate(dict(row))


class ClientConsentBody(BaseModel):
    consent: bool
    source: DeskConsentSource | None = Field(
        default=None,
        description="How the client agreed (signed form, said so in person, other); "
        "required when recording an agreement, so it cannot be ticked without a source",
    )


class ConsentEvent(BaseModel):
    id: UUID
    action: Literal["granted", "withdrawn"]
    source: ConsentSource
    recorded_by_name: str | None
    created_at: datetime


@router.put("/{client_id}/marketing-consent")
def set_client_marketing_consent(
    client_id: UUID, body: ClientConsentBody, request: Request, context: WriteDep
) -> Client:
    """Record that the client agreed to (or stopped) marketing messages, e.g. at the desk. An
    agreement needs a source; a client who stopped ads with the opt-out link agrees again only
    by their own choice, so the desk records it with a source too."""
    ensure_not_erased(context.session, client_id)
    if body.consent and body.source is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="consent_source_required"
        )
    address, device = request_origin(request)
    context.session.execute(
        text("SELECT app.set_client_consent(:id, :consent, :source, :ip, :ua)"),
        {
            "id": client_id,
            "consent": body.consent,
            "source": body.source or "desk_other",
            "ip": address,
            "ua": device,
        },
    )
    return get_client(client_id, context)


@router.get("/{client_id}/consent-events")
def client_consent_events(client_id: UUID, context: ReadDep) -> list[ConsentEvent]:
    """The trail of this client's marketing consent, newest first."""
    rows = context.session.execute(
        text("""
            SELECT e.id, e.action, e.source, e.created_at,
                   coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1))
                       AS recorded_by_name
            FROM app.consent_events e
            LEFT JOIN app.users u ON u.id = e.recorded_by
            WHERE e.client_id = :id
            ORDER BY e.created_at DESC, e.id LIMIT 50
        """),
        {"id": client_id},
    ).mappings()
    return [ConsentEvent.model_validate(dict(r)) for r in rows]


@router.patch("/{client_id}")
def update_client(client_id: UUID, body: ClientUpdate, context: WriteDep) -> Client:
    ensure_not_erased(context.session, client_id)
    home = context.session.execute(
        text("SELECT home_location_id FROM app.clients WHERE id = :id"), {"id": client_id}
    ).first()
    if home is not None:
        ensure_branch_visible(context, home.home_location_id)
    changes = body.model_dump(exclude_unset=True)
    ensure_branch_allowed(context, changes.get("home_location_id"))
    if "first_name" in changes and not changes["first_name"]:
        raise HTTPException(status_code=422, detail="first_name must not be blank")
    if "status" in changes and changes["status"] is None:
        del changes["status"]
    if "custom_fields" in changes:
        changes["custom_fields"] = _custom_fields(context.session, changes["custom_fields"])
    assignments = set_clause(changes, ClientUpdate.model_fields, casts={"custom_fields": "jsonb"})
    sql = f"UPDATE app.clients SET {assignments} WHERE id = :id RETURNING {COLUMNS}"
    try:
        row = (
            context.session.execute(
                text(sql),
                {**changes, "id": client_id},
            )
            .mappings()
            .first()
        )
    except IntegrityError as error:
        raise _email_taken(error) or error from error
    if row is None:
        raise not_found()
    _join_home_branch(context.session, client_id, row["home_location_id"])
    return Client.model_validate(dict(row))
