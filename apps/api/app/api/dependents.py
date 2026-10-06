"""Dependents (#43, decision X10): the pets or children a client brings.

A dependent is a profile under a client: who actually comes (Rex the dog, Noa the daughter),
while the client books and pays. The business's industry pack says which kind it keeps
(`dependents`: pet or child) and which extra details it asks for (`dependent_fields`: breed,
weight, allergies). Staff manage every client's dependents; clients manage their own in the
app. Dependents are never deleted (their visits keep the name): they are made inactive."""

import datetime as dt
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.bookings import tenant_pack
from app.api.clients import ClientFieldDefinition
from app.api.common import blank_to_none, ensure_not_erased, not_found, set_clause
from app.api.deps import ClientDep, TenantContext, require
from app.permissions import Permission
from app.verticals import clean_fields

router = APIRouter(tags=["dependents"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

FieldValue = str | int | None


class Dependent(BaseModel):
    id: UUID
    client_id: UUID
    kind: Literal["pet", "child"]
    name: str
    birth_date: dt.date | None
    details: dict[str, str | int] = Field(description="Values of the pack's dependent fields")
    notes: str | None
    active: bool
    created_at: datetime


class DependentSettings(BaseModel):
    """What the business's industry keeps about dependents (labels come from translations:
    the kind's words under terms, the fields under clientFields)."""

    kind: Literal["pet", "child"] | None = Field(description="None: the industry keeps none")
    required: bool = Field(description="Every booking must say which pet / child comes")
    fields: list[ClientFieldDefinition]


class DependentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_date: dt.date | None = None
    details: dict[str, FieldValue] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "notes", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return blank_to_none(value)


class DependentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    birth_date: dt.date | None = None
    details: dict[str, FieldValue] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None

    @field_validator("name", "notes", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return blank_to_none(value)


COLUMNS = "id, client_id, kind, name, birth_date, details, notes, active, created_at"


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _details(db: Session, tenant_id: UUID, values: dict[str, FieldValue]) -> str:
    """The values validated against the pack's dependent fields, as JSON for the column."""
    try:
        return json.dumps(clean_fields(tenant_pack(db, tenant_id).dependent_fields, values))
    except ValueError as error:
        raise _unprocessable(str(error)) from error


def _kind(db: Session, tenant_id: UUID) -> str:
    kind = tenant_pack(db, tenant_id).dependents
    if kind is None:  # this industry doesn't keep pets or children
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="dependents_off")
    return kind


def _settings(db: Session, tenant_id: UUID) -> DependentSettings:
    pack = tenant_pack(db, tenant_id)
    return DependentSettings(
        kind=pack.dependents,  # type: ignore[arg-type]
        required=pack.dependent_required,
        fields=[
            ClientFieldDefinition(
                key=f.key,
                kind=f.kind,  # type: ignore[arg-type]
                options=list(f.options),
                max_length=f.max_length,
            )
            for f in pack.dependent_fields
        ],
    )


def _list(db: Session, client_id: UUID) -> list[Dependent]:
    rows = db.execute(
        text(f"""
            SELECT {COLUMNS} FROM app.dependents
            WHERE client_id = :client_id
            ORDER BY NOT active, name, created_at
        """),
        {"client_id": client_id},
    ).mappings()
    return [Dependent.model_validate(dict(row)) for row in rows]


def _create(db: Session, tenant_id: UUID, client_id: UUID, body: DependentCreate) -> Dependent:
    ensure_not_erased(db, client_id)
    if body.name is None:
        raise _unprocessable("name must not be blank")
    try:
        row = (
            db.execute(
                text(f"""
                    INSERT INTO app.dependents
                        (tenant_id, client_id, kind, name, birth_date, details, notes)
                    VALUES (:tenant_id, :client_id, :kind, :name, :birth_date,
                            CAST(:details AS jsonb), :notes)
                    RETURNING {COLUMNS}
                """),
                {
                    "tenant_id": tenant_id,
                    "client_id": client_id,
                    "kind": _kind(db, tenant_id),
                    "name": body.name,
                    "birth_date": body.birth_date,
                    "details": _details(db, tenant_id, body.details),
                    "notes": body.notes,
                },
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:  # no such client in this business
        raise not_found() from error
    return Dependent.model_validate(dict(row))


def _update(db: Session, tenant_id: UUID, dependent_id: UUID, body: DependentUpdate) -> Dependent:
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise _unprocessable("name must not be blank")
    if "active" in changes and changes["active"] is None:
        del changes["active"]
    if "details" in changes:
        changes["details"] = _details(db, tenant_id, changes["details"] or {})
    if not changes:
        row = db.execute(
            text(f"SELECT {COLUMNS} FROM app.dependents WHERE id = :id"), {"id": dependent_id}
        )
    else:
        assignments = set_clause(changes, casts={"details": "jsonb"})
        row = db.execute(
            text(f"UPDATE app.dependents SET {assignments} WHERE id = :id RETURNING {COLUMNS}"),
            {**changes, "id": dependent_id},
        )
    found = row.mappings().first()
    if found is None:
        raise not_found()
    return Dependent.model_validate(dict(found))


# --- Staff ------------------------------------------------------------------------------------


@router.get("/dependents/settings")
def dependent_settings(context: ReadDep) -> DependentSettings:
    return _settings(context.session, context.tenant_id)


@router.get("/clients/{client_id}/dependents")
def client_dependents(client_id: UUID, context: ReadDep) -> list[Dependent]:
    """The client's pets / children, active first."""
    return _list(context.session, client_id)


@router.post("/clients/{client_id}/dependents", status_code=status.HTTP_201_CREATED)
def add_dependent(client_id: UUID, body: DependentCreate, context: WriteDep) -> Dependent:
    return _create(context.session, context.tenant_id, client_id, body)


@router.patch("/dependents/{dependent_id}")
def update_dependent(dependent_id: UUID, body: DependentUpdate, context: WriteDep) -> Dependent:
    return _update(context.session, context.tenant_id, dependent_id, body)


# --- Client app -------------------------------------------------------------------------------


@client_router.get("/dependents/settings")
def my_dependent_settings(context: ClientDep) -> DependentSettings:
    return _settings(context.session, context.tenant_id)


@client_router.get("/dependents")
def my_dependents(context: ClientDep) -> list[Dependent]:
    """The signed-in client's pets / children in this business."""
    return _list(context.session, context.client_id)


@client_router.post("/dependents", status_code=status.HTTP_201_CREATED)
def add_my_dependent(body: DependentCreate, context: ClientDep) -> Dependent:
    return _create(context.session, context.tenant_id, context.client_id, body)


@client_router.patch("/dependents/{dependent_id}")
def update_my_dependent(dependent_id: UUID, body: DependentUpdate, context: ClientDep) -> Dependent:
    # The client policy only lets a client see (and so change) their own dependents.
    return _update(context.session, context.tenant_id, dependent_id, body)
