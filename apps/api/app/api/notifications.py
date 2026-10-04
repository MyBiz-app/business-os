"""The client's notification inbox in the client app."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import ClientDep

router = APIRouter(prefix="/client", tags=["client"])

NotificationKind = Literal[
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
]


class Notification(BaseModel):
    id: UUID
    kind: NotificationKind
    payload: dict[str, Any] = Field(
        description="session_id, service_name, starts_at (and previous_starts_at, status or "
        "note, by kind)"
    )
    created_at: datetime
    read_at: datetime | None


class Inbox(BaseModel):
    unread: int
    items: list[Notification] = Field(description="The latest 50, newest first")


class MarkRead(BaseModel):
    ids: list[UUID] | None = Field(default=None, description="Omit to mark all as read")


def _inbox(context: ClientDep) -> Inbox:
    db = context.session
    rows = db.execute(
        text("""
            SELECT id, kind, payload, created_at, read_at FROM app.notifications
            WHERE client_id = app.current_client_id()
            ORDER BY created_at DESC LIMIT 50
        """)
    ).mappings()
    unread = db.execute(
        text("""
            SELECT count(*) FROM app.notifications
            WHERE client_id = app.current_client_id() AND read_at IS NULL
        """)
    ).scalar_one()
    return Inbox(unread=unread, items=[Notification.model_validate(dict(row)) for row in rows])


@router.get("/notifications")
def my_notifications(context: ClientDep) -> Inbox:
    return _inbox(context)


@router.post("/notifications/read")
def mark_read(body: MarkRead, context: ClientDep) -> Inbox:
    context.session.execute(
        text("""
            UPDATE app.notifications SET read_at = now()
            WHERE client_id = app.current_client_id() AND read_at IS NULL
              AND (CAST(:ids AS uuid[]) IS NULL OR id = ANY(CAST(:ids AS uuid[])))
        """),
        {"ids": [str(i) for i in body.ids] if body.ids is not None else None},
    )
    return _inbox(context)
