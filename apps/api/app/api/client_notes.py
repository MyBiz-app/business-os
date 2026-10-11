"""Visit notes: a per-client log written by staff (treatment notes, service history, trainer
notes), optionally about one of the client's bookings (migration 0030).

Reading needs `clients.read`. Writing needs `clients.write` or `bookings.manage`, so the staff
who see clients at their appointments (instructors, barbers, therapists) can log what they did.
Authors can delete their own notes; `clients.write` can delete any."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import ensure_not_erased, not_found
from app.api.deps import TenantContext, TenantDep, require
from app.core.permissions import Permission

router = APIRouter(prefix="/clients/{client_id}/notes", tags=["clients"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]


def _writer(context: TenantDep) -> TenantContext:
    allowed = {Permission.CLIENTS_WRITE.value, Permission.BOOKINGS_MANAGE.value}
    if not allowed & context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return context


WriteDep = Annotated[TenantContext, Depends(_writer)]


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    booking_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("body must not be blank")
        return value


class ClientNote(BaseModel):
    id: UUID
    body: str
    booking_id: UUID | None
    service_name: str | None = Field(description="The booked service, when about a booking")
    session_starts_at: datetime | None
    author_user_id: UUID | None
    author_name: str | None
    created_at: datetime


SELECT = """
    SELECT n.id, n.body, n.booking_id, sv.name AS service_name, s.starts_at AS session_starts_at,
           n.author_user_id,
           coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1)) AS author_name,
           n.created_at
    FROM app.client_notes n
    LEFT JOIN app.users u ON u.id = n.author_user_id
    LEFT JOIN app.bookings b ON b.id = n.booking_id
    LEFT JOIN app.sessions s ON s.id = b.session_id
    LEFT JOIN app.services sv ON sv.id = s.service_id
"""


def _client_exists(db: Session, client_id: UUID) -> None:
    if (
        db.execute(text("SELECT 1 FROM app.clients WHERE id = :id"), {"id": client_id}).scalar()
        is None
    ):
        raise not_found()


@router.get("")
def list_notes(client_id: UUID, context: ReadDep) -> list[ClientNote]:
    db = context.session
    _client_exists(db, client_id)
    rows = db.execute(
        text(f"{SELECT} WHERE n.client_id = :id ORDER BY n.created_at DESC LIMIT 200"),
        {"id": client_id},
    ).mappings()
    return [ClientNote.model_validate(dict(r)) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_note(client_id: UUID, body: NoteCreate, context: WriteDep) -> ClientNote:
    db = context.session
    _client_exists(db, client_id)
    ensure_not_erased(db, client_id)
    if body.booking_id is not None:
        mine = db.execute(
            text("SELECT 1 FROM app.bookings WHERE id = :b AND client_id = :c"),
            {"b": body.booking_id, "c": client_id},
        ).scalar()
        if mine is None:
            raise HTTPException(status_code=422, detail="booking_not_of_client")
    note_id = db.execute(
        text("""
            INSERT INTO app.client_notes (tenant_id, client_id, booking_id, author_user_id, body)
            VALUES (:t, :c, :b, app.current_user_id(), :body) RETURNING id
        """),
        {"t": context.tenant_id, "c": client_id, "b": body.booking_id, "body": body.body},
    ).scalar_one()
    row = db.execute(text(f"{SELECT} WHERE n.id = :id"), {"id": note_id}).mappings().one()
    return ClientNote.model_validate(dict(row))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(client_id: UUID, note_id: UUID, context: WriteDep) -> None:
    db = context.session
    author = db.execute(
        text("""
            SELECT author_user_id = app.current_user_id() FROM app.client_notes
            WHERE id = :id AND client_id = :c
        """),
        {"id": note_id, "c": client_id},
    ).first()
    if author is None:
        raise not_found()
    if not author[0] and Permission.CLIENTS_WRITE.value not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    db.execute(text("DELETE FROM app.client_notes WHERE id = :id"), {"id": note_id})
