"""Recording client notifications (see migration 0017). The client app renders the text.

Notifications describe what the studio did to the client's bookings or declarations; the
client's own actions don't notify them."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

SESSION_SNAPSHOT = """
    SELECT s.id AS session_id, sv.name AS service_name, s.starts_at
    FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
    WHERE s.id = :id
"""


def session_snapshot(db: Session, session_id: UUID) -> dict[str, Any]:
    row = db.execute(text(SESSION_SNAPSHOT), {"id": session_id}).mappings().one()
    return {**row, "session_id": str(row["session_id"]), "starts_at": row["starts_at"].isoformat()}


def notify(
    db: Session, tenant_id: UUID, client_ids: list[UUID], kind: str, payload: dict[str, Any]
) -> None:
    if not client_ids:
        return
    db.execute(
        text("""
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            VALUES (:tenant_id, :client_id, :kind, :payload)
        """),
        [
            {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "kind": kind,
                "payload": json.dumps(payload, default=str),
            }
            for client_id in client_ids
        ],
    )


def live_clients(db: Session, session_id: UUID) -> list[UUID]:
    """Clients with a booking or waitlist place in the session."""
    return list(
        db.execute(
            text("""
                SELECT client_id FROM app.bookings
                WHERE session_id = :id AND status IN ('booked', 'waitlisted')
            """),
            {"id": session_id},
        ).scalars()
    )


def notify_booking(db: Session, booking_id: UUID, kind: str) -> None:
    """The studio booked or cancelled this booking for the client (upcoming sessions only)."""
    row = db.execute(
        text("""
            SELECT b.tenant_id, b.client_id, b.session_id, b.status, s.starts_at > now() AS ahead
            FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id WHERE b.id = :id
        """),
        {"id": booking_id},
    ).one()
    if not row.ahead:
        return
    payload = {**session_snapshot(db, row.session_id), "status": row.status}
    notify(db, row.tenant_id, [row.client_id], kind, payload)


def notify_sessions(
    db: Session,
    tenant_id: UUID,
    kind: str,
    session_ids: list[UUID],
    previous_starts_at: list[Any] | None = None,
) -> None:
    """Tells every live client of each session at once (a closed day, a moved series): one
    insert for all of them instead of three queries per session. The payload matches
    `session_snapshot`, plus `previous_starts_at` when the sessions moved."""
    if not session_ids:
        return
    db.execute(
        text("""
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT :tenant_id, b.client_id, :kind,
                   jsonb_build_object(
                       'session_id', s.id::text, 'service_name', sv.name, 'starts_at', s.starts_at
                   ) || CASE WHEN t.previous IS NULL THEN '{}'::jsonb
                             ELSE jsonb_build_object('previous_starts_at', t.previous) END
            FROM unnest(CAST(:ids AS uuid[]), CAST(:previous AS timestamptz[])) AS t(id, previous)
            JOIN app.sessions s ON s.id = t.id
            JOIN app.services sv ON sv.id = s.service_id
            JOIN app.bookings b ON b.session_id = s.id AND b.status IN ('booked', 'waitlisted')
            ORDER BY s.starts_at, b.created_at
        """),
        {
            "tenant_id": tenant_id,
            "kind": kind,
            "ids": [str(i) for i in session_ids],
            "previous": previous_starts_at or [None] * len(session_ids),
        },
    )
