"""Tools the WhatsApp assistant may call (client-facing only)."""

import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.messaging.whatsapp_ai.base import OFFER_TTL, BotContext, ToolError, _local, _uuid

# --- Tools (client-facing only) ----------------------------------------------------------------


def business_info(ctx: BotContext, _args: dict[str, Any]) -> dict[str, Any]:
    rows = ctx.db.execute(
        text("""
            SELECT name, description, duration_minutes, price_amount, price_currency
            FROM app.services WHERE tenant_id = :t AND active AND booking_mode = 'class'
            ORDER BY name LIMIT 30
        """),
        {"t": ctx.business.tenant_id},
    ).mappings()
    return {
        "business": ctx.business.name,
        "services": [
            {
                "name": r["name"],
                "description": r["description"],
                "minutes": r["duration_minutes"],
                "price": r["price_amount"],
                "currency": r["price_currency"],
            }
            for r in rows
        ],
        "note": "Prices are in minor units: divide by 100.",
    }


# Bookable: an upcoming, not cancelled class (appointments are booked at a free time instead).
SLOTS = text("""
    SELECT s.id, sv.name AS service, s.starts_at, s.ends_at, s.capacity,
           (SELECT booked FROM app.session_counts(s.id)) AS booked
    FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
    WHERE s.status <> 'cancelled' AND sv.booking_mode = 'class' AND s.starts_at > now()
      AND s.tenant_id = :t AND s.starts_at >= :start AND s.starts_at < :end
    ORDER BY s.starts_at LIMIT 200
""")
SLOT = text("""
    SELECT s.id, sv.name AS service, s.starts_at, s.ends_at, s.capacity,
           (SELECT booked FROM app.session_counts(s.id)) AS booked
    FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
    WHERE s.status <> 'cancelled' AND sv.booking_mode = 'class' AND s.starts_at > now()
      AND s.tenant_id = :t AND s.id = :id
""")


def free_slots(ctx: BotContext, args: dict[str, Any]) -> dict[str, Any]:
    try:
        start = dt.date.fromisoformat(args["start_date"])
    except ValueError as error:
        raise ToolError("start_date must be a date like 2026-10-03") from error
    days = min(max(int(args["days"]), 1), 14)
    zone = ZoneInfo(ctx.business.time_zone)
    window_start = dt.datetime.combine(start, dt.time.min, tzinfo=zone)
    rows = ctx.db.execute(
        SLOTS,
        {
            "t": ctx.business.tenant_id,
            "start": window_start,
            "end": window_start + dt.timedelta(days=days),
        },
    ).mappings()
    slots = [
        {
            "session_id": str(r["id"]),
            "service": r["service"],
            "starts": _local(r["starts_at"], ctx.business.time_zone),
            "ends": _local(r["ends_at"], ctx.business.time_zone)[-5:],
            "spots_left": r["capacity"] - r["booked"],
        }
        for r in rows
        if r["booked"] < r["capacity"]
    ]
    return {"free": slots[:40]}


def my_bookings(ctx: BotContext, _args: dict[str, Any]) -> dict[str, Any]:
    rows = ctx.db.execute(
        text("""
            SELECT sv.name AS service, s.starts_at, b.status
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = :client AND b.status IN ('booked', 'waitlisted')
              AND s.starts_at > now()
            ORDER BY s.starts_at LIMIT 20
        """),
        {"client": ctx.client_id},
    ).mappings()
    return {
        "bookings": [
            {
                "service": r["service"],
                "starts": _local(r["starts_at"], ctx.business.time_zone),
                "status": r["status"],
            }
            for r in rows
        ]
    }


def _bookable(db: Session, tenant_id: UUID, session_id: UUID) -> dict[str, Any]:
    row = db.execute(SLOT, {"t": tenant_id, "id": session_id}).mappings().first()
    if row is None:
        raise ToolError("no upcoming session with that id: use an id from free_slots")
    return dict(row)


def _already_booked(db: Session, session_id: UUID, client_id: UUID) -> bool:
    return (
        db.execute(
            text("""
                SELECT 1 FROM app.bookings
                WHERE session_id = :s AND client_id = :c AND status <> 'cancelled'
            """),
            {"s": session_id, "c": client_id},
        ).first()
        is not None
    )


def payload_hash(kind: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"kind": kind, "payload": payload}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def offer_booking(ctx: BotContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = _uuid(args["session_id"])
    session = _bookable(ctx.db, ctx.business.tenant_id, session_id)
    if _already_booked(ctx.db, session_id, ctx.client_id):
        raise ToolError("the client is already booked for that session")
    preview = {
        "service": session["service"],
        "starts": _local(session["starts_at"], ctx.business.time_zone),
        "full": session["booked"] >= session["capacity"],
    }
    payload = {"session_id": str(session_id)}
    # One live offer per conversation: a new one replaces the last.
    ctx.db.execute(
        text("""
            UPDATE app.whatsapp_offers SET status = 'replaced', decided_at = now()
            WHERE conversation_id = :c AND status = 'pending'
        """),
        {"c": ctx.conversation_id},
    )
    offer_id = ctx.db.execute(
        text("""
            INSERT INTO app.whatsapp_offers
                (tenant_id, conversation_id, client_id, kind, payload, payload_hash, preview,
                 expires_at)
            VALUES (:t, :c, :client, 'book_session', :payload, :hash, :preview, now() + :ttl)
            RETURNING id
        """),
        {
            "t": ctx.business.tenant_id,
            "c": ctx.conversation_id,
            "client": ctx.client_id,
            "payload": json.dumps(payload),
            "hash": payload_hash("book_session", payload),
            "preview": json.dumps(preview),
            "ttl": OFFER_TTL,
        },
    ).scalar_one()
    return {
        "offer_id": str(offer_id),
        "status": "waiting_for_client_confirmation",
        "preview": preview,
        "instruction": "Nothing is booked yet. A line asking the client to reply 1 to confirm is "
        "added under your message; do not repeat it and do not claim it is booked.",
    }


DATE = {"type": "string", "description": "Local date, YYYY-MM-DD"}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    run: Callable[[BotContext, dict[str, Any]], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.properties),
                "additionalProperties": False,
            },
        }


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            "business_info",
            "The business's name and the classes it offers, with length and price.",
            {},
            business_info,
        ),
        Tool(
            "free_slots",
            "Upcoming classes with free spots, from start_date for 1-14 days. Times are local.",
            {"start_date": DATE, "days": {"type": "integer"}},
            free_slots,
        ),
        Tool(
            "my_bookings",
            "This client's own upcoming bookings (and waiting-list places).",
            {},
            my_bookings,
        ),
        Tool(
            "offer_booking",
            "Offers the client a place in one session (an id from free_slots). Books nothing: "
            "the client confirms by replying 1.",
            {"session_id": {"type": "string", "description": "A session_id from free_slots"}},
            offer_booking,
        ),
    )
}
DEFINITIONS = [tool.definition() for tool in TOOLS.values()]


def run_tool(ctx: BotContext, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Runs a tool for the model. Returns (result, is_error); never raises for tool errors."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": "no such tool"}, True
    try:
        with ctx.db.begin_nested():  # a failed tool leaves no partial writes
            return tool.run(ctx, args), False
    except ToolError as error:
        return {"error": str(error)}, True
    except (KeyError, ValueError, TypeError):  # the model left out or garbled an input
        return {"error": "invalid input"}, True
