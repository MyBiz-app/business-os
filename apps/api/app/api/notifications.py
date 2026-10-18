"""The client's notification inbox in the client app."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import ClientDep
from app.api.pagination import DEFAULT_LIMIT, KeysetDep, KeysetPage, encode_cursor

router = APIRouter(prefix="/client", tags=["client"])

NotificationKind = Literal[
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
    "plan_ending",
    "friend_request",
    "class_invite",
    "waitlist_spot_open",
    "waitlist_spot_taken",
]


class Notification(BaseModel):
    id: UUID
    kind: NotificationKind
    payload: dict[str, Any] = Field(
        description="session_id, service_name, starts_at (and previous_starts_at, status or "
        "note, by kind); plan_ending: plan_name, ends_on; friend_request: from_name; "
        "class_invite: from_name, invite_id, session_id, service_name, starts_at; "
        "waitlist_spot_open: session_id, service_name, starts_at, ends_at"
    )
    created_at: datetime
    read_at: datetime | None


class Inbox(BaseModel):
    unread: int
    items: list[Notification] = Field(description="Newest first, one page")
    next_cursor: str | None = Field(
        default=None, description="Pass as `after` for the next (older) page"
    )


class MarkRead(BaseModel):
    ids: list[UUID] | None = Field(default=None, description="Omit to mark all as read")


def _inbox(context: ClientDep, page: KeysetPage) -> Inbox:
    db = context.session
    after = page.after or [None, None]
    rows = list(
        db.execute(
            text("""
            SELECT id, kind, payload, created_at, read_at FROM app.notifications
            WHERE client_id = app.current_client_id()
              AND (CAST(:after_at AS timestamptz) IS NULL
                   OR (created_at, id) < (CAST(:after_at AS timestamptz), CAST(:after_id AS uuid)))
            ORDER BY created_at DESC, id DESC LIMIT :fetch OFFSET :offset
        """),
            {
                "fetch": page.fetch,
                "offset": page.offset,
                "after_at": after[0],
                "after_id": after[1] if len(after) > 1 else None,
            },
        ).mappings()
    )
    more = len(rows) > page.limit
    rows = rows[: page.limit]
    unread = db.execute(
        text("""
            SELECT count(*) FROM app.notifications
            WHERE client_id = app.current_client_id() AND read_at IS NULL
        """)
    ).scalar_one()
    return Inbox(
        unread=unread,
        items=[Notification.model_validate(dict(row)) for row in rows],
        next_cursor=encode_cursor(rows[-1]["created_at"].isoformat(), rows[-1]["id"])
        if more
        else None,
    )


@router.get("/notifications")
def my_notifications(context: ClientDep, page: KeysetDep) -> Inbox:
    return _inbox(context, page)


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
    return _inbox(context, KeysetPage(limit=DEFAULT_LIMIT, offset=0, after=None))
