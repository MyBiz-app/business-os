"""Tools the assistant can use. Every tool runs as the requesting user, inside their business,
with their permissions: the assistant can never do more than the user could in the app.

Read tools answer immediately. Write tools never act: they create a pending action with a
human-readable preview, which the user confirms in the app (see app/ai/actions.py)."""

import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text

from app.api import bookings as bookings_api
from app.api import plans as plans_api
from app.api import schedule as schedule_api
from app.api.deps import TenantContext
from app.metrics import METRICS, compute, previous_period
from app.permissions import Permission, role_allows

PENDING_ACTION_TTL = dt.timedelta(minutes=15)
MAX_ROWS = 25


@dataclass(frozen=True)
class ToolContext:
    tenant: TenantContext
    user_id: UUID
    conversation_id: UUID
    time_zone: str
    modules: set[str]


class ToolError(Exception):
    """A problem the model should see and can react to (bad id, not allowed, ...)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    permission: Permission
    run: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]
    module: str | None = None  # extra module the tool needs (actions need AI Pro)

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


def _local(instant: dt.datetime, time_zone: str) -> str:
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d %H:%M")


def _uuid(value: str, what: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ToolError(f"{what} is not a valid id") from error


def _date(value: str, what: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise ToolError(f"{what} must be a date like 2026-10-03") from error


# --- Read tools ------------------------------------------------------------------------------


def find_clients(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    pattern = "%" + args["query"].strip().replace("\\", "\\\\").replace("%", "\\%") + "%"
    rows = ctx.tenant.session.execute(
        text("""
            SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name, c.status
            FROM app.clients c
            WHERE c.first_name || ' ' || coalesce(c.last_name, '') ILIKE :p
               OR c.email ILIKE :p OR c.phone ILIKE :p
            ORDER BY c.first_name, c.last_name LIMIT :limit
        """),
        {"p": pattern, "limit": MAX_ROWS},
    ).mappings()
    return {"clients": [{**dict(r), "id": str(r["id"])} for r in rows]}


def get_client(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    client_id = _uuid(args["client_id"], "client_id")
    db = ctx.tenant.session
    row = (
        db.execute(
            text("""
            SELECT trim(first_name || ' ' || coalesce(last_name, '')) AS name, status,
                   created_at::date AS joined
            FROM app.clients WHERE id = :id
        """),
            {"id": client_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ToolError("no client with that id")
    plans = [
        {
            "name": e.name,
            "state": e.state,
            "valid": f"{e.starts_on} to {e.ends_on}",
            "entries_left": e.credits_remaining,
        }
        for e in plans_api.list_entitlements(db, client_id)[:10]
    ]
    recent = db.execute(
        text("""
            SELECT sv.name AS service, s.starts_at, b.status, b.late_cancel
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = :id ORDER BY s.starts_at DESC LIMIT 10
        """),
        {"id": client_id},
    ).mappings()
    return {
        "name": row["name"],
        "status": row["status"],
        "joined": str(row["joined"]),
        "plans": plans,
        "recent_bookings": [
            {
                "service": b["service"],
                "starts": _local(b["starts_at"], ctx.time_zone),
                "status": b["status"],
                "late_cancel": b["late_cancel"],
            }
            for b in recent
        ],
    }


def list_sessions(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    start = _date(args["start_date"], "start_date")
    days = min(max(int(args["days"]), 1), 14)
    sessions = schedule_api.list_sessions(context=ctx.tenant, start=start, days=days)
    return {
        "sessions": [
            {
                "id": str(s.id),
                "service": s.service.name,
                "starts": _local(s.starts_at, ctx.time_zone),
                "ends": _local(s.ends_at, ctx.time_zone)[-5:],
                "room": s.room_name,
                "instructor": s.instructor_email,
                "booked": s.booked,
                "capacity": s.capacity,
                "waitlisted": s.waitlisted,
                "status": s.status,
            }
            for s in sessions[:60]
        ]
    }


def get_session_roster(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = _uuid(args["session_id"], "session_id")
    roster = bookings_api.list_bookings(session_id=session_id, context=ctx.tenant)
    return {
        "bookings": [
            {
                "booking_id": str(b.id),
                "client_id": str(b.client_id),
                "client": b.client_name,
                "status": b.status,
                "waitlist_position": b.waitlist_position,
                "plan": b.plan_name,
            }
            for b in roster
        ]
    }


def get_metrics(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    start, end = _date(args["start_date"], "start_date"), _date(args["end_date"], "end_date")
    if end < start or (end - start).days > 366:
        raise ToolError("the period must be 1 to 366 days, start before end")
    before_start, before_end = previous_period(start, end)
    db = ctx.tenant.session
    return {
        "period": f"{start} to {end}",
        "previous_period": f"{before_start} to {before_end}",
        "metrics": [
            {
                "metric": key,
                "unit": METRICS[key].unit,
                "value": compute(db, key, start, end),
                "previous": compute(db, key, before_start, before_end),
            }
            for key in args["metrics"]
        ],
        "note": "money is in minor units (divide by 100); percent is 0-100",
    }


def list_plans(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    plans = plans_api.list_plans(context=ctx.tenant, active=True)
    return {
        "plans": [
            {
                "name": p.name,
                "kind": p.kind,
                "price_minor_units": p.price_amount,
                "currency": p.price_currency,
                "validity_days": p.validity_days,
                "entries": p.credits,
            }
            for p in plans
        ]
    }


def client_sources(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    start, end = _date(args["start_date"], "start_date"), _date(args["end_date"], "end_date")
    rows = ctx.tenant.session.execute(
        text("""
            SELECT coalesce(c.source, 'unknown') AS source, count(*) AS new_clients,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM app.entitlements e WHERE e.client_id = c.id
                   )) AS bought_a_plan
            FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
            WHERE (c.created_at AT TIME ZONE t.time_zone)::date BETWEEN :start AND :end
            GROUP BY 1 ORDER BY 2 DESC
        """),
        {"start": start, "end": end},
    ).mappings()
    return {"period": f"{start} to {end}", "sources": [dict(r) for r in rows]}


def inactive_members(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    days = min(max(int(args["days"]), 7), 180)
    rows = ctx.tenant.session.execute(
        text("""
            SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name,
                   (SELECT max(s.starts_at) FROM app.bookings b
                    JOIN app.sessions s ON s.id = b.session_id
                    WHERE b.client_id = c.id AND b.status = 'checked_in') AS last_visit
            FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
            WHERE EXISTS (
                SELECT 1 FROM app.entitlements e
                WHERE e.client_id = c.id AND e.status = 'active'
                  AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on
            )
            AND NOT EXISTS (
                SELECT 1 FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
                WHERE b.client_id = c.id AND b.status = 'checked_in'
                  AND s.starts_at > now() - make_interval(days => :days)
            )
            ORDER BY last_visit NULLS FIRST LIMIT :limit
        """),
        {"days": days, "limit": MAX_ROWS},
    ).mappings()
    return {
        "members_with_a_valid_plan_and_no_visit_in_days": days,
        "members": [
            {
                "client_id": str(r["id"]),
                "name": r["name"],
                "last_visit": _local(r["last_visit"], ctx.time_zone)[:10]
                if r["last_visit"]
                else None,
            }
            for r in rows
        ],
    }


# --- Write tools: pending actions ------------------------------------------------------------


def payload_hash(tool_name: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": tool_name, "payload": payload}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _propose(
    ctx: ToolContext, tool_name: str, payload: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    action_id = ctx.tenant.session.execute(
        text("""
            INSERT INTO app.pending_actions
                (tenant_id, conversation_id, requested_by, agent_key, tool_name, payload,
                 payload_hash, preview, risk_level, expires_at)
            VALUES (:tenant_id, :conversation_id, :user_id, 'assistant', :tool, :payload,
                    :hash, :preview, 'low', now() + :ttl)
            RETURNING id
        """),
        {
            "tenant_id": ctx.tenant.tenant_id,
            "conversation_id": ctx.conversation_id,
            "user_id": ctx.user_id,
            "tool": tool_name,
            "payload": json.dumps(payload),
            "hash": payload_hash(tool_name, payload),
            "preview": json.dumps(preview),
            "ttl": PENDING_ACTION_TTL,
        },
    ).scalar_one()
    return {
        "pending_action_id": str(action_id),
        "status": "waiting_for_user_confirmation",
        "preview": preview,
        "instruction": "Nothing has happened yet. Tell the user to review and confirm the card "
        "shown under your message. Do not claim the action is done.",
    }


def _session_preview(ctx: ToolContext, session_id: UUID) -> dict[str, Any]:
    try:
        session = schedule_api.get_session(session_id=session_id, context=ctx.tenant)
    except HTTPException as error:
        raise ToolError("no session with that id") from error
    if session.status == "cancelled":
        raise ToolError("that session is cancelled")
    return {
        "service": session.service.name,
        "starts": _local(session.starts_at, ctx.time_zone),
        "booked": session.booked,
        "capacity": session.capacity,
    }


def book_client(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = _uuid(args["session_id"], "session_id")
    client_id = _uuid(args["client_id"], "client_id")
    client = get_client(ctx, {"client_id": str(client_id)})
    session = _session_preview(ctx, session_id)
    preview = {
        "kind": "book_client",
        "client": client["name"],
        **session,
        "full": session["booked"] >= session["capacity"],
    }
    payload = {"session_id": str(session_id), "client_id": str(client_id)}
    return _propose(ctx, "book_client", payload, preview)


def cancel_booking(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    booking_id = _uuid(args["booking_id"], "booking_id")
    row = (
        ctx.tenant.session.execute(
            text("""
            SELECT b.session_id, b.status,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client
            FROM app.bookings b JOIN app.clients c ON c.id = b.client_id WHERE b.id = :id
        """),
            {"id": booking_id},
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] == "cancelled":
        raise ToolError("no active booking with that id")
    preview = {
        "kind": "cancel_booking",
        "client": row["client"],
        **_session_preview(ctx, row["session_id"]),
    }
    return _propose(ctx, "cancel_booking", {"booking_id": str(booking_id)}, preview)


DATE = {"type": "string", "description": "Local date, YYYY-MM-DD"}
ID = {"type": "string", "description": "An id returned by another tool"}

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            "find_clients",
            "Search the business's clients by part of a name, email or phone number.",
            {"query": {"type": "string"}},
            Permission.CLIENTS_READ,
            find_clients,
        ),
        Tool(
            "get_client",
            "A client's status, plans (memberships, punch cards) and 10 most recent bookings.",
            {"client_id": ID},
            Permission.CLIENTS_READ,
            get_client,
        ),
        Tool(
            "list_sessions",
            "Scheduled sessions (classes) from start_date for 1-14 days, with bookings and "
            "capacity. Times are local.",
            {"start_date": DATE, "days": {"type": "integer"}},
            Permission.SCHEDULE_READ,
            list_sessions,
        ),
        Tool(
            "get_session_roster",
            "Who is booked or waitlisted in one session, with booking ids.",
            {"session_id": ID},
            Permission.SCHEDULE_READ,
            get_session_roster,
        ),
        Tool(
            "get_metrics",
            "Business metrics for a period of local dates (inclusive) and the period of the same "
            "length before it. Definitions: "
            + "; ".join(f"{m.key}: {m.description}" for m in METRICS.values()),
            {
                "metrics": {"type": "array", "items": {"type": "string", "enum": list(METRICS)}},
                "start_date": DATE,
                "end_date": DATE,
            },
            Permission.REPORTS_READ,
            get_metrics,
        ),
        Tool(
            "client_sources",
            "New clients in a period by where they came from (lead source), and how many of "
            "them bought a plan.",
            {"start_date": DATE, "end_date": DATE},
            Permission.REPORTS_READ,
            client_sources,
        ),
        Tool(
            "inactive_members",
            "Members who hold a valid plan but have not come in for at least `days` days "
            "(7-180), longest absence first.",
            {"days": {"type": "integer"}},
            Permission.CLIENTS_READ,
            inactive_members,
        ),
        Tool(
            "list_plans",
            "The memberships and punch cards the business sells, with prices.",
            {},
            Permission.CATALOG_READ,
            list_plans,
        ),
        Tool(
            "book_client",
            "Propose booking a client into a session (waitlist if full). Creates a card the user "
            "must confirm; nothing is booked until they do.",
            {"session_id": ID, "client_id": ID},
            Permission.BOOKINGS_MANAGE,
            book_client,
            module="ai_pro",
        ),
        Tool(
            "cancel_booking",
            "Propose cancelling a booking. Creates a card the user must confirm.",
            {"booking_id": ID},
            Permission.BOOKINGS_MANAGE,
            cancel_booking,
            module="ai_pro",
        ),
    )
}


def _allowed(tool: Tool, role: str, modules: set[str]) -> bool:
    return role_allows(role, tool.permission) and (tool.module is None or tool.module in modules)


def tools_for(role: str, modules: set[str]) -> list[Tool]:
    """Only the tools the user's role and the business's modules allow are offered."""
    return [tool for tool in TOOLS.values() if _allowed(tool, role, modules)]


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Runs a tool for the model. Returns (result, is_error); never raises for tool errors."""
    tool = TOOLS.get(name)
    if tool is None or not _allowed(tool, ctx.tenant.role, ctx.modules):
        return {"error": "this tool is not available to the user"}, True
    try:
        with ctx.tenant.session.begin_nested():  # a failed tool leaves no partial writes
            return tool.run(ctx, args), False
    except ToolError as error:
        return {"error": str(error)}, True
    except HTTPException as error:
        return {"error": str(error.detail)}, True
