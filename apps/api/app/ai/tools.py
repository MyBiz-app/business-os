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
from app.api import resources as resources_api
from app.api import schedule as schedule_api
from app.api import time_billing as time_api
from app.api.deps import TenantContext
from app.metrics import METRICS, compute, members_at_risk, previous_period
from app.permissions import Permission

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
    feature: str | None = None  # an industry feature it needs (e.g. time_billing)

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
            WHERE c.erased_at IS NULL
              AND (c.first_name || ' ' || coalesce(c.last_name, '') ILIKE :p
                   OR c.email ILIKE :p OR c.phone ILIKE :p)
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
                   created_at::date AS joined, custom_fields
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
    notes = db.execute(
        text("""
            SELECT body, created_at::date AS day FROM app.client_notes
            WHERE client_id = :id ORDER BY created_at DESC LIMIT 5
        """),
        {"id": client_id},
    ).mappings()
    dependents = db.execute(
        text("""
            SELECT id, kind, name, details FROM app.dependents
            WHERE client_id = :id AND active ORDER BY name
        """),
        {"id": client_id},
    ).mappings()
    return {
        "name": row["name"],
        "status": row["status"],
        "joined": str(row["joined"]),
        "pets_or_children (book one with its id)": [
            {"id": str(d["id"]), "kind": d["kind"], "name": d["name"], "details": d["details"]}
            for d in dependents
        ],
        "profile (the industry's extra fields)": row["custom_fields"],
        "latest_visit_notes": [{"day": str(n["day"]), "note": n["body"]} for n in notes],
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


def free_courts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Free times of the courts and rooms rented by the hour, on one day, for one length."""
    day = _date(args["date"], "date")
    db = ctx.tenant.session
    found = []
    for service in resources_api._services(db):
        if not service.rooms:
            continue
        lengths = resources_api.lengths(service)
        minutes = int(args["minutes"]) if int(args["minutes"]) in lengths else lengths[0]
        slots = resources_api.resource_slots(db, service.id, day, minutes, None)
        found.append(
            {
                "service": service.name,
                "price_per_hour": service.price_per_hour,
                "currency": service.price_currency,
                "lengths_minutes": lengths,
                "minutes": minutes,
                "free": [
                    {
                        "room": slot.room_name,
                        "starts": _local(slot.starts_at, ctx.time_zone)[-5:],
                        "price": slot.price_amount,
                    }
                    for slot in slots[:40]
                ],
            }
        )
    return {"date": day.isoformat(), "services": found}


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
    members = [
        m for m in members_at_risk(ctx.tenant.session, days, limit=500) if m.reason == "inactive"
    ][:MAX_ROWS]
    return {
        "members_with_a_valid_plan_and_no_visit_in_days": days,
        "members": [
            {
                "client_id": m.client_id,
                "name": m.name,
                "last_visit": m.last_visit.isoformat() if m.last_visit else None,
            }
            for m in members
        ],
    }


def lead_pipeline(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    """Open leads by stage, and who is due a follow-up (CRM module)."""
    db = ctx.tenant.session
    stages = db.execute(
        text("""
            SELECT stage, count(*) AS leads FROM app.leads
            WHERE stage NOT IN ('won', 'lost') OR stage_changed_at > now() - interval '30 days'
            GROUP BY 1
        """)
    ).mappings()
    due = db.execute(
        text("""
            SELECT l.id AS lead_id, trim(l.first_name || ' ' || coalesce(l.last_name, '')) AS name,
                   l.stage, l.follow_up_on, l.interest, l.phone
            FROM app.leads l JOIN app.tenants t ON t.id = l.tenant_id
            WHERE l.stage NOT IN ('won', 'lost')
              AND l.follow_up_on <= (now() AT TIME ZONE t.time_zone)::date
            ORDER BY l.follow_up_on LIMIT :limit
        """),
        {"limit": MAX_ROWS},
    ).mappings()
    return {
        "leads_by_stage": [dict(r) for r in stages],
        "note": "Open stages count every open lead; won and lost count the last 30 days.",
        "follow_ups_due_today_or_overdue": [
            {**dict(r), "lead_id": str(r["lead_id"]), "follow_up_on": str(r["follow_up_on"])}
            for r in due
        ],
    }


# --- Write tools: pending actions ------------------------------------------------------------


def open_balances(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    """Quotes and bills: what clients still owe on accepted ones, and sent quotes awaiting an
    answer."""
    rows = ctx.tenant.session.execute(
        text("""
            SELECT q.number, q.kind, q.title, q.status, q.currency,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client,
                   app.quote_total(q.id) AS total, app.quote_paid(q.id) AS paid, q.sent_at
            FROM app.quotes q JOIN app.clients c ON c.id = q.client_id
            WHERE q.status IN ('sent', 'accepted')
            ORDER BY q.sent_at
        """)
    ).mappings()
    owed, awaiting = [], []
    for row in rows:
        item = {
            "number": row["number"],
            "kind": row["kind"],
            "client": row["client"],
            "title": row["title"],
            "total": row["total"],
            "currency": row["currency"],
        }
        if row["status"] == "accepted" and row["total"] > row["paid"]:
            owed.append({**item, "paid": row["paid"], "left": row["total"] - row["paid"]})
        elif row["status"] == "sent":
            awaiting.append(item)
    return {
        "amounts": "minor units",
        "owed_total": sum(o["left"] for o in owed),
        "owed": owed[:MAX_ROWS],
        "awaiting_answer": awaiting[:MAX_ROWS],
    }


def logged_time(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Time logged in a period: totals per client and per staff member, and what isn't billed."""
    start, end = _date(args["start_date"], "start_date"), _date(args["end_date"], "end_date")
    client_id = _uuid(args["client_id"], "client_id") if args.get("client_id") else None
    entries = time_api.time_entries(
        context=ctx.tenant, client_id=client_id, mine=False, start=start, end=end
    )
    per_client: dict[str, int] = {}
    per_staff: dict[str, int] = {}
    for entry in entries:
        per_client[entry.client_name] = per_client.get(entry.client_name, 0) + entry.minutes
        per_staff[entry.user_name] = per_staff.get(entry.user_name, 0) + entry.minutes
    unbilled = sum(e.minutes for e in entries if e.billable and e.bill_id is None)

    def top(totals: dict[str, int]) -> list[dict[str, Any]]:
        ranked = sorted(totals.items(), key=lambda item: -item[1])[:MAX_ROWS]
        return [{"name": name, "hours": round(minutes / 60, 2)} for name, minutes in ranked]

    return {
        "hours": round(sum(e.minutes for e in entries) / 60, 2),
        "billable_unbilled_hours": round(unbilled / 60, 2),
        "per_client": top(per_client),
        "per_staff": top(per_staff),
        "recent": [
            {
                "date": e.day.isoformat(),
                "client": e.client_name,
                "by": e.user_name,
                "hours": round(e.minutes / 60, 2),
                "description": e.description,
            }
            for e in entries[:10]
        ],
    }


def _month_arg(value: str) -> str:
    if not time_api.MONTH.fullmatch(value or ""):
        raise ToolError("month must be YYYY-MM")
    return value


def billing_preview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """What billing the month would bill each client (retainer fee and hours beyond it)."""
    rows = time_api.billing_preview(context=ctx.tenant, month=_month_arg(args["month"]))
    to_bill = [r for r in rows if not r.billed and r.total > 0]
    return {
        "amounts": "minor units",
        "clients_to_bill": len(to_bill),
        "total_to_bill": sum(r.total for r in to_bill),
        "already_billed": [r.client_name for r in rows if r.billed][:MAX_ROWS],
        "clients": [
            {
                "client_id": str(r.client_id),
                "name": r.client_name,
                "monthly_fee": r.monthly_amount,
                "hours_worked": round(r.worked_minutes / 60, 2),
                "hours_beyond": round(r.extra_minutes / 60, 2),
                "total": r.total,
            }
            for r in to_bill[:MAX_ROWS]
        ],
    }


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
    if args.get("dependent_id"):
        dependent_id = _uuid(args["dependent_id"], "dependent_id")
        name = ctx.tenant.session.execute(
            text("""
                SELECT name FROM app.dependents
                WHERE id = :id AND client_id = :client_id AND active
            """),
            {"id": dependent_id, "client_id": client_id},
        ).scalar()
        if name is None:
            raise ToolError("that pet / child is not one of this client's (see get_client)")
        preview["dependent"] = name
        payload["dependent_id"] = str(dependent_id)
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


def log_time(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    client_id = _uuid(args["client_id"], "client_id")
    client = get_client(ctx, {"client_id": str(client_id)})
    day = _date(args["date"], "date")
    minutes = args["minutes"]
    if not isinstance(minutes, int) or not 1 <= minutes <= 1440:
        raise ToolError("minutes must be between 1 and 1440")
    description = str(args["description"]).strip()[:500]
    if not description:
        raise ToolError("say what was done (description)")
    preview = {
        "kind": "log_time",
        "client": client["name"],
        "date": day.isoformat(),
        "hours": round(minutes / 60, 2),
        "description": description,
    }
    payload = {
        "client_id": str(client_id),
        "day": day.isoformat(),
        "minutes": minutes,
        "description": description,
    }
    return _propose(ctx, "log_time", payload, preview)


def bill_month(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    month = _month_arg(args["month"])
    rows = {
        str(r.client_id): r
        for r in time_api.billing_preview(context=ctx.tenant, month=month)
        if not r.billed and r.total > 0
    }
    wanted = args.get("client_ids") or list(rows)
    chosen = [rows[c] for c in dict.fromkeys(wanted) if c in rows]
    if not chosen:
        raise ToolError("nothing to bill for that month (see billing_preview)")
    preview = {
        "kind": "bill_month",
        "month": month,
        "clients": len(chosen),
        "names": [r.client_name for r in chosen][:5],
        "total": sum(r.total for r in chosen),
        "currency": chosen[0].currency,
    }
    payload = {"month": month, "client_ids": [str(r.client_id) for r in chosen]}
    return _propose(ctx, "bill_month", payload, preview)


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
            "A client's status, profile details (e.g. their car at a garage), latest visit notes, "
            "plans (memberships, punch cards) and 10 most recent bookings.",
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
            "free_courts",
            "Courts and rooms rented by the hour: for each such service, its price per hour "
            "(minor units), the lengths offered and the free start times per court on a local "
            "date for a length in minutes (the shortest offered when that length isn't).",
            {"date": DATE, "minutes": {"type": "integer"}},
            Permission.SCHEDULE_READ,
            free_courts,
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
            "lead_pipeline",
            "The CRM pipeline: how many leads are in each stage (new, contacted, trial, offer, "
            "won, lost) and which open leads are due a follow-up call today or overdue.",
            {},
            Permission.CLIENTS_READ,
            lead_pipeline,
            module="crm",
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
            "must confirm; nothing is booked until they do. In businesses that keep clients' pets "
            "or children, name the one who comes (ids from get_client), else an empty string.",
            {
                "session_id": ID,
                "client_id": ID,
                "dependent_id": {
                    "type": "string",
                    "description": "The pet / child who comes (an id from get_client), or ''",
                },
            },
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
        Tool(
            "open_balances",
            "Quotes and bills: what each client still owes on accepted ones (total, paid, left) "
            "and sent quotes still waiting for the client's answer.",
            {},
            Permission.SALES_MANAGE,
            open_balances,
        ),
        Tool(
            "logged_time",
            "Time staff logged for clients between two local dates (inclusive): hours per "
            "client and per staff member, billable hours not billed yet, and the latest entries. "
            "client_id narrows it to one client, or ''.",
            {"start_date": DATE, "end_date": DATE, "client_id": {**ID, "description": "or ''"}},
            Permission.CLIENTS_READ,
            logged_time,
            feature="time_billing",
        ),
        Tool(
            "billing_preview",
            "Billing a month (YYYY-MM): each client with a retainer or unbilled time, the "
            "monthly fee, hours worked and beyond the retainer, and the total; who is billed.",
            {"month": {"type": "string", "description": "YYYY-MM"}},
            Permission.SALES_MANAGE,
            billing_preview,
            feature="time_billing",
        ),
        Tool(
            "log_time",
            "Propose logging the user's own time for a client: a local date, minutes and what "
            "was done. Creates a card the user must confirm.",
            {
                "client_id": ID,
                "date": DATE,
                "minutes": {"type": "integer"},
                "description": {"type": "string"},
            },
            Permission.CLIENTS_READ,
            log_time,
            module="ai_pro",
            feature="time_billing",
        ),
        Tool(
            "bill_month",
            "Propose billing a month (YYYY-MM) for clients (ids from billing_preview; an empty "
            "list bills everyone not billed yet). Each gets a bill they pay by its link. "
            "Creates a card the user must confirm.",
            {
                "month": {"type": "string", "description": "YYYY-MM"},
                "client_ids": {"type": "array", "items": {"type": "string"}},
            },
            Permission.SALES_MANAGE,
            bill_month,
            module="ai_pro",
            feature="time_billing",
        ),
    )
}


def _allowed(tool: Tool, permissions: frozenset[str], modules: set[str]) -> bool:
    return (
        tool.permission in permissions
        and (tool.module is None or tool.module in modules)
        and (tool.feature is None or tool.feature in modules)
    )


def tools_for(permissions: frozenset[str], modules: set[str]) -> list[Tool]:
    """Only the tools the user's permissions and the business's modules (and its industry's
    features, given in the same set) allow are offered."""
    return [tool for tool in TOOLS.values() if _allowed(tool, permissions, modules)]


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Runs a tool for the model. Returns (result, is_error); never raises for tool errors."""
    tool = TOOLS.get(name)
    if tool is None or not _allowed(tool, ctx.tenant.permissions, ctx.modules):
        return {"error": "this tool is not available to the user"}, True
    try:
        with ctx.tenant.session.begin_nested():  # a failed tool leaves no partial writes
            return tool.run(ctx, args), False
    except ToolError as error:
        return {"error": str(error)}, True
    except HTTPException as error:
        return {"error": str(error.detail)}, True
    except KeyError as error:  # the model left out a required input
        return {"error": f"missing input: {error.args[0]}"}, True
