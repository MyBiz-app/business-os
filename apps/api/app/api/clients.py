from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(prefix="/clients", tags=["clients"])

ClientStatus = Literal["active", "inactive", "lead"]

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

COLUMNS = (
    "id, first_name, last_name, email, phone, date_of_birth, notes, status, created_at, updated_at"
)


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ClientFields(BaseModel):
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("last_name", "email", "phone", "notes", "date_of_birth", mode="before")
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return _blank_to_none(value)


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
    created_at: datetime
    updated_at: datetime


class ClientPage(BaseModel):
    items: list[Client]
    total: int


def _email_taken(error: IntegrityError) -> HTTPException | None:
    if "clients_tenant_email_key" in str(error.orig):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")
    return None


def _like_pattern(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("")
def list_clients(
    context: ReadDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    client_status: Annotated[ClientStatus | None, Query(alias="status")] = None,
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
                         status)
                    VALUES
                        (:tenant_id, :first_name, :last_name, :email, :phone, :date_of_birth,
                         :notes, :status)
                    RETURNING {COLUMNS}
                """),
                {**body.model_dump(), "tenant_id": context.tenant_id},
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return Client.model_validate(dict(row))


@router.patch("/{client_id}")
def update_client(client_id: UUID, body: ClientUpdate, context: WriteDep) -> Client:
    changes = body.model_dump(exclude_unset=True)
    if "first_name" in changes and not changes["first_name"]:
        raise HTTPException(status_code=422, detail="first_name must not be blank")
    if "status" in changes and changes["status"] is None:
        del changes["status"]
    # Column names come from the model's fields, never from user input.
    assignments = ", ".join(f"{column} = :{column}" for column in changes)
    set_clause = f"{assignments}, updated_at = now()" if assignments else "updated_at = now()"
    try:
        row = (
            context.session.execute(
                text(f"UPDATE app.clients SET {set_clause} WHERE id = :id RETURNING {COLUMNS}"),
                {**changes, "id": client_id},
            )
            .mappings()
            .first()
        )
    except IntegrityError as error:
        raise _email_taken(error) or error from error
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return Client.model_validate(dict(row))
