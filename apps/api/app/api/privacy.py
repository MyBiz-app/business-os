"""Privacy requests about one client: export everything we hold, or erase their personal data.

Erasure keeps the client row (as "Deleted client") so bookings, plans and payments keep their
history; payments must be kept for accounting. It clears the personal fields, removes health
declarations and notifications, frees upcoming bookings and unlinks the client app account.
Both actions are for owners (permission `clients.privacy`) and are written to the audit log."""

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.bookings import cancel_booking, lock_session
from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(prefix="/clients", tags=["clients"])

PrivacyDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_PRIVACY))]

# The name an erased client is shown with, in the business's language (content, like plans).
ERASED_NAME = {"he": "לקוח/ה שנמחק/ה", "en": "Deleted client"}


def _rows(db: Session, sql: str, client_id: UUID) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(text(sql), {"id": client_id}).mappings()]


def _audit(db: Session, tenant_id: UUID, action: str, client_id: UUID, details: dict) -> None:
    db.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (:tenant_id, 'user', app.current_user_id(), :action, 'client', :client_id,
                    :details)
        """),
        {
            "tenant_id": tenant_id,
            "action": action,
            "client_id": client_id,
            "details": json.dumps(details),
        },
    )


def _client(db: Session, client_id: UUID, lock: bool = False) -> dict[str, Any]:
    row = (
        db.execute(
            text(f"""
                SELECT id, first_name, last_name, email, phone, date_of_birth, notes, status,
                       source, user_id IS NOT NULL AS uses_client_app, created_at, updated_at,
                       erased_at
                FROM app.clients WHERE id = :id {"FOR UPDATE" if lock else ""}
            """),
            {"id": client_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


@router.get("/{client_id}/export")
def export_client(client_id: UUID, context: PrivacyDep) -> dict[str, Any]:
    """Everything the business holds about the client, as one JSON document."""
    db = context.session
    business = db.execute(
        text("SELECT name FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    document = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "business": business,
        "client": _client(db, client_id),
        "bookings": _rows(
            db,
            """
            SELECT sv.name AS service, s.starts_at, s.ends_at, b.status, b.late_cancel,
                   b.checked_in_at, b.cancelled_at, b.created_at
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = :id ORDER BY s.starts_at
            """,
            client_id,
        ),
        "plans": _rows(
            db,
            """
            SELECT e.name, e.kind, e.credits, e.starts_on, e.ends_on, e.status,
                   e.price_amount, e.price_currency, e.created_at,
                   coalesce((SELECT json_agg(json_build_object(
                                 'starts_on', f.starts_on, 'ends_on', f.ends_on,
                                 'reason', f.reason) ORDER BY f.starts_on)
                             FROM app.entitlement_freezes f WHERE f.entitlement_id = e.id),
                            '[]') AS freezes
            FROM app.entitlements e WHERE e.client_id = :id ORDER BY e.created_at
            """,
            client_id,
        ),
        "payments": _rows(
            db,
            """
            SELECT amount, currency, status, provider, created_at
            FROM app.payments WHERE client_id = :id ORDER BY created_at
            """,
            client_id,
        ),
        "notifications": _rows(
            db,
            """
            SELECT kind, payload, created_at, read_at
            FROM app.notifications WHERE client_id = :id ORDER BY created_at
            """,
            client_id,
        ),
        "receipts": _rows(
            db,
            """
            SELECT number, issued_at, description, amount, currency, method, simulated
            FROM app.receipts WHERE client_id = :id ORDER BY number
            """,
            client_id,
        ),
        "leads": _rows(
            db,
            """
            SELECT l.first_name, l.last_name, l.email, l.phone, l.interest, l.source, l.stage,
                   l.created_at,
                   (SELECT coalesce(json_agg(json_build_object(
                        'kind', a.kind, 'note', a.note, 'occurred_at', a.occurred_at)
                        ORDER BY a.occurred_at), '[]')
                    FROM app.lead_activities a WHERE a.lead_id = l.id) AS activities
            FROM app.leads l WHERE l.client_id = :id ORDER BY l.created_at
            """,
            client_id,
        ),
        "health_declarations": _rows(
            db,
            """
            SELECT form_key, locale, answers, statement, signed_name, signed_at, valid_until,
                   status, reviewed_at, review_note
            FROM app.health_declarations WHERE client_id = :id ORDER BY signed_at
            """,
            client_id,
        ),
    }
    _audit(db, context.tenant_id, "clients.export", client_id, {})
    # Dates and UUIDs become strings; the response is a plain JSON document.
    return json.loads(json.dumps(document, default=str, ensure_ascii=False))


class EraseRequest(BaseModel):
    confirm: bool = Field(description="Must be true: erasing cannot be undone")


class EraseResult(BaseModel):
    cancelled_bookings: int
    removed_health_declarations: int


@router.post("/{client_id}/erase")
def erase_client(client_id: UUID, body: EraseRequest, context: PrivacyDep) -> EraseResult:
    if not body.confirm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="confirm")
    db = context.session
    client = _client(db, client_id, lock=True)
    if client["erased_at"] is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_erased")

    upcoming = db.execute(
        text("""
            SELECT b.id, b.session_id FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            WHERE b.client_id = :id AND b.status IN ('booked', 'waitlisted')
              AND s.starts_at > now()
            ORDER BY b.session_id
        """),
        {"id": client_id},
    ).all()
    for booking_id, session_id in upcoming:
        lock_session(db, session_id)
        cancel_booking(db, booking_id, session_id)

    removed = db.execute(
        text("DELETE FROM app.health_declarations WHERE client_id = :id"), {"id": client_id}
    ).rowcount
    db.execute(text("DELETE FROM app.notifications WHERE client_id = :id"), {"id": client_id})
    # The CRM history that led to the client (their inquiry, calls, notes) goes with them.
    db.execute(text("DELETE FROM app.leads WHERE client_id = :id"), {"id": client_id})
    db.execute(
        text("""
            UPDATE app.entitlement_freezes SET reason = NULL
            WHERE entitlement_id IN (SELECT id FROM app.entitlements WHERE client_id = :id)
        """),
        {"id": client_id},
    )
    locale = db.execute(
        text("SELECT locale FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    db.execute(
        text("""
            UPDATE app.clients
            SET first_name = :name, last_name = NULL, email = NULL, phone = NULL,
                date_of_birth = NULL, notes = NULL, status = 'inactive', user_id = NULL,
                erased_at = now(), updated_at = now()
            WHERE id = :id
        """),
        {"name": ERASED_NAME.get(locale, ERASED_NAME["en"]), "id": client_id},
    )
    db.execute(
        text(
            "UPDATE app.receipts SET client_name = :name, client_email = NULL WHERE client_id = :id"
        ),
        {"name": ERASED_NAME.get(locale, ERASED_NAME["en"]), "id": client_id},
    )
    result = EraseResult(cancelled_bookings=len(upcoming), removed_health_declarations=removed)
    _audit(db, context.tenant_id, "clients.erase", client_id, result.model_dump())
    return result
