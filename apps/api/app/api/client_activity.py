"""A client's activity timeline: one newest-first feed of what happened to them, gathered from
the tables that already hold it (bookings, payments, plans, messages, notes, the history of a
lead they came from). Nothing is stored for it, so there is no migration.

Needs `clients.read`; a member kept to some branches gets "not found" for another branch's client
and sees only the bookings made at their branches. Messages appear only when the business has the
messaging module."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.common import not_found
from app.api.deps import TenantContext, ensure_client_visible, has_module, require
from app.api.pagination import PageDep
from app.core.permissions import Permission

router = APIRouter(prefix="/clients/{client_id}/activity", tags=["clients"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]

ActivityKind = Literal["booking", "payment", "plan", "message", "note", "lead"]


class ActivityEvent(BaseModel):
    id: str = Field(description="Unique within the feed: `<kind>:<row id>[/<part>]`")
    kind: ActivityKind
    status: str | None = Field(
        description="Booking status, payment status, plan event (sold, cancelled), message "
        "channel, lead event (created, stage, note, ...)"
    )
    title: str | None = Field(description="Service, plan or message text; null for a bare event")
    detail: str | None = Field(description="Note text, lead stage or message body")
    amount: int | None = Field(description="Minor units, for payments and plan sales")
    currency: str | None
    ref_id: UUID | None = Field(description="The booking, payment, plan, message or note")
    occurred_at: datetime


FEED = " UNION ALL ".join(
    f"({part})"
    for part in [
        """
        SELECT 'booking:' || b.id AS id, 'booking' AS kind, b.status AS status,
               sv.name AS title, NULL AS detail, NULL::integer AS amount, NULL AS currency,
               b.id AS ref_id, coalesce(b.checked_in_at, b.cancelled_at, b.created_at) AS at
        FROM app.bookings b
        JOIN app.sessions s ON s.id = b.session_id
        JOIN app.services sv ON sv.id = s.service_id
        WHERE b.client_id = :id AND (s.location_id IS NULL OR app.in_branch(s.location_id))
        """,
        """
        SELECT 'payment:' || p.id, 'payment', p.status, e.name, NULL, p.amount,
               p.currency::text, p.id, p.created_at
        FROM app.payments p
        LEFT JOIN app.entitlements e ON e.id = p.entitlement_id
        WHERE p.client_id = :id
        """,
        """
        SELECT 'plan:' || e.id || '/sold', 'plan', 'sold', e.name, NULL, e.price_amount,
               e.price_currency::text, e.id, e.created_at
        FROM app.entitlements e WHERE e.client_id = :id
        UNION ALL
        SELECT 'plan:' || e.id || '/cancelled', 'plan', 'cancelled', e.name, NULL, NULL, NULL,
               e.id, e.cancelled_at
        FROM app.entitlements e WHERE e.client_id = :id AND e.cancelled_at IS NOT NULL
        """,
        """
        SELECT 'note:' || n.id, 'note', NULL, sv.name, n.body, NULL, NULL, n.id, n.created_at
        FROM app.client_notes n
        LEFT JOIN app.bookings b ON b.id = n.booking_id
        LEFT JOIN app.sessions s ON s.id = b.session_id
        LEFT JOIN app.services sv ON sv.id = s.service_id
        WHERE n.client_id = :id
        """,
        """
        SELECT 'lead:' || a.id, 'lead', a.kind, NULL, coalesce(a.note, a.to_stage), NULL, NULL,
               a.id, a.occurred_at
        FROM app.lead_activities a
        JOIN app.leads l ON l.id = a.lead_id
        WHERE l.client_id = :id
        """,
        # Messages show only for a business with the messaging module (`:with_messages`).
        """
        SELECT 'message:' || m.id, 'message', m.channel, NULL, m.body, NULL, NULL, m.id,
               m.created_at
        FROM app.messages m WHERE m.client_id = :id AND :with_messages
        """,
    ]
)

QUERY = (
    "SELECT id, kind, status, title, detail, amount, currency, ref_id, at AS occurred_at "
    f"FROM ({FEED}) feed ORDER BY at DESC, id LIMIT :limit OFFSET :offset"
)


@router.get("")
def client_activity(client_id: UUID, context: ReadDep, page: PageDep) -> list[ActivityEvent]:
    """Newest first. Page with `limit` and `offset`."""
    db = context.session
    ensure_client_visible(context, client_id)
    if (
        db.execute(text("SELECT 1 FROM app.clients WHERE id = :id"), {"id": client_id}).first()
        is None
    ):
        raise not_found()
    rows = db.execute(
        text(QUERY),
        {
            "id": client_id,
            "with_messages": has_module(db, "whatsapp"),
            "limit": page.limit,
            "offset": page.offset,
        },
    ).mappings()
    return [ActivityEvent.model_validate(dict(r)) for r in rows]
