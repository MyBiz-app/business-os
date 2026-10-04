import json
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, ensure_not_erased, not_found, set_clause
from app.api.deps import TenantContext, require
from app.permissions import Permission
from app.verticals import VERTICAL_PACKS, VerticalPack, clean_client_fields

router = APIRouter(prefix="/clients", tags=["clients"])

ClientStatus = Literal["active", "inactive", "lead"]
ClientSource = Literal[
    "walk_in", "referral", "instagram", "facebook", "google", "website", "app", "other"
]

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

COLUMNS = (
    "id, first_name, last_name, email, phone, date_of_birth, notes, status, source, "
    "custom_fields, created_at, updated_at, erased_at"
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
    created_at: datetime
    updated_at: datetime
    erased_at: datetime | None = Field(description="Personal data erased on request (privacy)")


class ClientPage(BaseModel):
    items: list[Client]
    total: int


def _email_taken(error: IntegrityError) -> HTTPException | None:
    if "clients_tenant_email_key" in str(error.orig):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")
    return None


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


def _like_pattern(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("")
def list_clients(
    context: ReadDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    client_status: Annotated[ClientStatus | None, Query(alias="status")] = None,
    plan: Annotated[
        Literal["valid", "none"] | None,
        Query(description="valid: holds a plan valid today; none: doesn't"),
    ] = None,
    absent_days: Annotated[
        int | None, Query(ge=1, le=365, description="No check-in in this many days")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ClientPage:
    # RLS limits rows to the current tenant; the filters below narrow further.
    where = "WHERE TRUE"
    params: dict[str, object] = {"limit": limit, "offset": offset}
    if search and search.strip():
        where += """ AND concat_ws(' ', first_name, last_name, email, phone) ILIKE :pattern"""
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
    rows = session.execute(
        text(f"""
            SELECT {COLUMNS} FROM app.clients {where}
            ORDER BY first_name, last_name NULLS FIRST, created_at
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return ClientPage(items=[Client.model_validate(dict(row)) for row in rows], total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, context: WriteDep) -> Client:
    try:
        row = (
            context.session.execute(
                text(f"""
                    INSERT INTO app.clients
                        (tenant_id, first_name, last_name, email, phone, date_of_birth, notes,
                         status, source, custom_fields)
                    VALUES
                        (:tenant_id, :first_name, :last_name, :email, :phone, :date_of_birth,
                         :notes, :status, :source, CAST(:custom_fields AS jsonb))
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
    return Client.model_validate(dict(row))


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
    return Client.model_validate(dict(row))


@router.patch("/{client_id}")
def update_client(client_id: UUID, body: ClientUpdate, context: WriteDep) -> Client:
    ensure_not_erased(context.session, client_id)
    changes = body.model_dump(exclude_unset=True)
    if "first_name" in changes and not changes["first_name"]:
        raise HTTPException(status_code=422, detail="first_name must not be blank")
    if "status" in changes and changes["status"] is None:
        del changes["status"]
    if "custom_fields" in changes:
        changes["custom_fields"] = _custom_fields(context.session, changes["custom_fields"])
    assignments = set_clause(changes, casts={"custom_fields": "jsonb"})
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
    return Client.model_validate(dict(row))
