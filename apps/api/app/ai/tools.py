"""Tools the assistant can use. Every tool runs as the requesting user, inside their business,
with their permissions: the assistant can never do more than the user could in the app.

Read tools answer immediately. Write tools never act: they create a pending action with a
human-readable preview, which the user confirms in the app (see app/ai/actions.py)."""

import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text

from app.ai import scheduled
from app.ai.scope import CLIENT_IN_SCOPE, visible_clients
from app.api import bookings as bookings_api
from app.api import plans as plans_api
from app.api import resources as resources_api
from app.api import schedule as schedule_api
from app.api import time_billing as time_api
from app.api.deps import TenantContext
from app.api.pagination import Page
from app.core.permissions import Permission
from app.reports.metrics import METRICS, compute, members_at_risk, previous_period
from app.social import studio
from app.social.providers import NETWORK_KEYS

PENDING_ACTION_TTL = dt.timedelta(minutes=15)
MAX_ROWS = 25
MAX_ROSTER = 200


@dataclass(frozen=True)
class ToolContext:
    tenant: TenantContext
    user_id: UUID
    conversation_id: UUID
    time_zone: str
    modules: set[str]
    # The agent talking (its key is filed on the actions it proposes) and the agents the user
    # may be handed over to.
    agent_key: str = "chief"
    handoff_keys: frozenset[str] = frozenset()
    # Where a hand-over to a key really goes (a team's lead stands in for its members).
    handoff_via: dict[str, str] = field(default_factory=dict)
    # How long a card this conversation proposes stays open (a scheduled run nobody watches
    # leaves its cards for days).
    pending_ttl: dt.timedelta = PENDING_ACTION_TTL


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
        text(
            """
            SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name, c.status
            FROM app.clients c
            WHERE c.erased_at IS NULL
              AND (c.first_name || ' ' || coalesce(c.last_name, '') ILIKE :p
                   OR c.email ILIKE :p OR c.phone ILIKE :p)
              AND """
            + CLIENT_IN_SCOPE
            + """
            ORDER BY c.first_name, c.last_name LIMIT :limit
        """
        ),
        {"p": pattern, "limit": MAX_ROWS},
    ).mappings()
    return {"clients": [{**dict(r), "id": str(r["id"])} for r in rows]}


def get_client(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    client_id = _uuid(args["client_id"], "client_id")
    db = ctx.tenant.session
    if not visible_clients(db, [client_id]):  # another branch's client looks like no client
        raise ToolError("no client with that id")
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
    roster = bookings_api.list_bookings(
        session_id=session_id, context=ctx.tenant, page=Page(limit=MAX_ROSTER, offset=0)
    )
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
        text(
            """
            SELECT coalesce(c.source, 'unknown') AS source, count(*) AS new_clients,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM app.entitlements e WHERE e.client_id = c.id
                   )) AS bought_a_plan
            FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
            WHERE (c.created_at AT TIME ZONE t.time_zone)::date BETWEEN :start AND :end
              AND """
            + CLIENT_IN_SCOPE
            + """
            GROUP BY 1 ORDER BY 2 DESC
        """
        ),
        {"start": start, "end": end},
    ).mappings()
    return {"period": f"{start} to {end}", "sources": [dict(r) for r in rows]}


def inactive_members(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    days = min(max(int(args["days"]), 7), 180)
    at_risk = [
        m for m in members_at_risk(ctx.tenant.session, days, limit=500) if m.reason == "inactive"
    ]
    visible = visible_clients(ctx.tenant.session, [UUID(m.client_id) for m in at_risk])
    members = [m for m in at_risk if UUID(m.client_id) in visible][:MAX_ROWS]
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
        text(
            """
            SELECT q.number, q.kind, q.title, q.status, q.currency,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client,
                   app.quote_total(q.id) AS total, app.quote_paid(q.id) AS paid, q.sent_at
            FROM app.quotes q JOIN app.clients c ON c.id = q.client_id
            WHERE q.status IN ('sent', 'accepted') AND """
            + CLIENT_IN_SCOPE
            + """
            ORDER BY q.sent_at
        """
        )
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
        context=ctx.tenant,
        client_id=client_id,
        mine=False,
        start=start,
        end=end,
        page=Page(limit=500, offset=0),
    )
    visible = visible_clients(ctx.tenant.session, list({e.client_id for e in entries}))
    entries = [e for e in entries if e.client_id in visible]
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


def _billable_clients(ctx: ToolContext, month: str) -> list[time_api.BillPreview]:
    """The month's billing preview, for the clients in the current branches only."""
    rows = time_api.billing_preview(context=ctx.tenant, month=month)
    visible = visible_clients(ctx.tenant.session, [r.client_id for r in rows])
    return [r for r in rows if r.client_id in visible]


def billing_preview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """What billing the month would bill each client (retainer fee and hours beyond it)."""
    rows = _billable_clients(ctx, _month_arg(args["month"]))
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
            VALUES (:tenant_id, :conversation_id, :user_id, :agent, :tool, :payload,
                    :hash, :preview, 'low', now() + :ttl)
            RETURNING id
        """),
        {
            "tenant_id": ctx.tenant.tenant_id,
            "conversation_id": ctx.conversation_id,
            "user_id": ctx.user_id,
            "agent": ctx.agent_key,
            "tool": tool_name,
            "payload": json.dumps(payload),
            "hash": payload_hash(tool_name, payload),
            "preview": json.dumps(preview),
            "ttl": ctx.pending_ttl,
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
        str(r.client_id): r for r in _billable_clients(ctx, month) if not r.billed and r.total > 0
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


def suggest_agent(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Offers the user a hand-over to a specialist agent. Nothing is switched: the app shows a
    card and the user decides."""
    key = str(args["agent_key"])
    if key not in ctx.handoff_keys:
        raise ToolError("that agent is not available to this user; answer it yourself")
    reason = str(args["reason"]).strip()[:300]
    if not reason:
        raise ToolError("say in a sentence why that agent fits")
    key = ctx.handoff_via.get(key, key)
    return {
        "agent_suggestion": {"agent_key": key, "reason": reason},
        "instruction": "The user sees a card offering the hand-over. Tell them in a sentence who "
        "can take it from here and why; do not claim anything was switched.",
    }


def _dry_run(ctx: ToolContext, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Runs a write tool only to learn what it would propose (payload, hash, preview), then
    throws the proposed card away. The tool's own checks decide whether the request is valid."""
    db = ctx.tenant.session
    tool = TOOLS[tool_name]
    if tool.permission not in ctx.tenant.permissions or (
        tool.module is not None and tool.module not in ctx.modules
    ):
        raise ToolError("the user cannot run that action")
    attempt = db.begin_nested()
    try:
        card = tool.run(ctx, args)
        row = (
            db.execute(
                text(
                    "SELECT payload, payload_hash, preview FROM app.pending_actions WHERE id = :id"
                ),
                {"id": card["pending_action_id"]},
            )
            .mappings()
            .one()
        )
        return dict(row)
    finally:
        attempt.rollback()


def schedule_task(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    kind = str(args["kind"])
    if kind not in scheduled.KINDS:
        raise ToolError("kind must be action or agent_run")
    title = str(args["title"]).strip()[:120]
    if not title:
        raise ToolError("give the task a short title")
    weekdays = args["weekdays"] if isinstance(args["weekdays"], list) else []
    try:
        schedule = scheduled.build_schedule(
            str(args["frequency"]),
            str(args["time"]),
            str(args["date"]) or None,
            weekdays,
            args["day_of_month"] or None,
        )
        first = scheduled.next_run(schedule, ctx.time_zone, dt.datetime.now(dt.UTC))
        if first is None:
            raise scheduled.ScheduleError("that time has already passed")
        scheduled.check_limit(ctx.tenant.session, ctx.modules)
    except scheduled.ScheduleError as error:
        raise ToolError(str(error)) from error
    spec: dict[str, Any] = {"kind": kind, "title": title, "schedule": schedule}
    preview: dict[str, Any] = {
        "kind": "schedule_task",
        "task_kind": kind,
        "title": title,
        "schedule": schedule,
        "first_run": _local(first, ctx.time_zone),
    }
    if kind == "agent_run":
        instruction = str(args["instruction"]).strip()[:2000]
        if not instruction:
            raise ToolError("say what the agent should do (instruction)")
        spec["instruction"] = instruction
        spec["max_credits"] = scheduled.DEFAULT_MAX_CREDITS
        preview["instruction"] = instruction
        preview["max_credits"] = scheduled.DEFAULT_MAX_CREDITS
    else:
        name = str(args["action_tool"])
        if name not in scheduled.SCHEDULABLE_TOOLS:
            raise ToolError(
                "that action cannot be scheduled; " + ", ".join(sorted(scheduled.SCHEDULABLE_TOOLS))
            )
        try:
            action_args = json.loads(str(args["action_args_json"]) or "{}")
        except ValueError as error:
            raise ToolError("action_args_json must be a JSON object") from error
        if not isinstance(action_args, dict):
            raise ToolError("action_args_json must be a JSON object")
        proposed = _dry_run(ctx, name, action_args)
        spec.update(
            tool_name=name,
            payload=proposed["payload"],
            payload_hash=proposed["payload_hash"],
            preview=proposed["preview"],
        )
        preview["action"] = proposed["preview"]
    return _propose(ctx, "schedule_task", spec, preview)


def list_scheduled_tasks(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    rows = ctx.tenant.session.execute(
        text("""
            SELECT id, title, kind, status, schedule, next_run_at FROM app.ai_scheduled_tasks
            WHERE created_by = :user AND status IN ('active', 'paused')
            ORDER BY next_run_at NULLS LAST LIMIT :limit
        """),
        {"user": ctx.user_id, "limit": MAX_ROWS},
    ).mappings()
    return {
        "tasks": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "kind": r["kind"],
                "status": r["status"],
                "schedule": r["schedule"],
                "next_run": _local(r["next_run_at"], ctx.time_zone) if r["next_run_at"] else None,
            }
            for r in rows
        ]
    }


def cancel_scheduled_task(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    task_id = _uuid(args["task_id"], "task_id")
    row = ctx.tenant.session.execute(
        text("""
            SELECT title FROM app.ai_scheduled_tasks
            WHERE id = :id AND created_by = :user AND status IN ('active', 'paused')
        """),
        {"id": task_id, "user": ctx.user_id},
    ).first()
    if row is None:
        raise ToolError("no scheduled task of the user with that id (see list_scheduled_tasks)")
    preview = {"kind": "cancel_scheduled_task", "title": row.title}
    return _propose(ctx, "cancel_scheduled_task", {"task_id": str(task_id)}, preview)


def _network(args: dict[str, Any]) -> str:
    value = str(args["network"]).strip()
    if value and value not in NETWORK_KEYS:
        raise ToolError(f"unknown network; use one of: {', '.join(NETWORK_KEYS)} or '' for all")
    return value


def _studio_accounts(ctx: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    return studio.visible_accounts(ctx.tenant.session, ctx.tenant.branches, _network(args))


def _today(ctx: ToolContext) -> dt.date:
    return dt.datetime.now(ZoneInfo(ctx.time_zone)).date()


def social_overview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return studio.overview(
        ctx.tenant.session,
        _studio_accounts(ctx, args),
        int(args["days"]),
        _today(ctx),
        ctx.time_zone,
    )


def top_posts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sort = str(args["sort"])
    if sort not in ("views", "engagement"):
        raise ToolError("sort must be 'views' or 'engagement'")
    posts = studio.best_posts(
        ctx.tenant.session,
        _studio_accounts(ctx, args),
        int(args["days"]),
        _today(ctx),
        sort,
        int(args["limit"]),
    )
    return {"posts": posts}


def audience_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "audience": studio.audience_summary(ctx.tenant.session, _studio_accounts(ctx, args)),
        "note": "percent of the audience; only where the network shares it",
    }


def draft_post(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = str(args["text"]).strip()
    if not 1 <= len(body) <= 2200:
        raise ToolError("the post text must be 1 to 2200 characters")
    image_url = str(args["image_url"]).strip()
    if image_url and not image_url.startswith("https://"):
        raise ToolError("image_url must be an https link, or ''")
    idea = str(args["idea"]).strip()[:300]
    draft_id = studio.save_draft(
        ctx.tenant.session,
        ctx.user_id,
        ctx.agent_key,
        _network(args) or None,
        body,
        image_url or None,
        idea or None,
    )
    return {
        "draft_id": str(draft_id),
        "saved": True,
        "instruction": "The draft is saved, not published. Tell the owner it waits in their "
        "content drafts and offer to publish it (that needs their confirmation).",
    }


def list_drafts(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    return {
        "drafts": [
            {
                "draft_id": str(d["id"]),
                "network": d["network"],
                "text": d["body"][:500],
                "has_image": bool(d["image_url"]),
                "idea": d["idea"],
            }
            for d in studio.open_drafts(ctx.tenant.session)
        ]
    }


def publish_post(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    draft_id, account_id = (
        _uuid(args["draft_id"], "draft_id"),
        _uuid(args["account_id"], "account_id"),
    )
    draft = studio.get_draft(ctx.tenant.session, draft_id)
    if draft is None or draft["status"] != "draft":
        raise ToolError("that draft is not open (not found, published or discarded)")
    account = next(
        (
            a
            for a in studio.visible_accounts(ctx.tenant.session, ctx.tenant.branches)
            if a["id"] == account_id
        ),
        None,
    )
    if account is None:
        raise ToolError("no such connected account (ids come from social_overview)")
    if draft["network"] and draft["network"] != account["network"]:
        raise ToolError("the draft was written for another network")
    if not studio.can_publish(account):
        raise ToolError("this account cannot publish: demo data, not reconnected, or no support")
    preview = {
        "kind": "publish_post",
        "network": account["network"],
        "account": account["name"],
        "text": draft["body"][:300],
        "image_url": draft["image_url"],
    }
    payload = {"draft_id": str(draft_id), "account_id": str(account_id)}
    return _propose(ctx, "publish_post", payload, preview)


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
        Tool(
            "social_overview",
            "The business's connected social accounts (ids, networks, whether each can publish) "
            "and their summed numbers for the last N days (1-90) against the period before: "
            "followers, reach, views, video views, engagement, link clicks, the content kinds "
            "that work and the best times to post. network is facebook, instagram, threads, "
            "youtube, tiktok or google_business, or '' for all.",
            {"network": {"type": "string"}, "days": {"type": "integer"}},
            Permission.SOCIAL_READ,
            social_overview,
            module="social_studio",
        ),
        Tool(
            "top_posts",
            "The best posts and videos of the last N days (1-90), sorted by 'views' or "
            "'engagement', at most `limit` (1-10). network '' is all.",
            {
                "network": {"type": "string"},
                "days": {"type": "integer"},
                "sort": {"type": "string", "description": "'views' or 'engagement'"},
                "limit": {"type": "integer"},
            },
            Permission.SOCIAL_READ,
            top_posts,
            module="social_studio",
        ),
        Tool(
            "audience_summary",
            "Who follows the accounts: the biggest age, gender and city groups. network '' is all.",
            {"network": {"type": "string"}},
            Permission.SOCIAL_READ,
            audience_summary,
            module="social_studio",
        ),
        Tool(
            "draft_post",
            "Save a post draft for the owner (nothing is published). network is the one it is "
            "written for or ''; image_url is an https link or ''; idea is one line on why it "
            "should work or ''.",
            {
                "network": {"type": "string"},
                "text": {"type": "string"},
                "image_url": {"type": "string"},
                "idea": {"type": "string"},
            },
            Permission.SOCIAL_MANAGE,
            draft_post,
            module="social_studio",
        ),
        Tool(
            "list_drafts",
            "The owner's open post drafts (newest first, at most 10), with the ids needed to "
            "publish one.",
            {},
            Permission.SOCIAL_READ,
            list_drafts,
            module="social_studio",
        ),
        Tool(
            "publish_post",
            "Propose publishing an open draft on a connected account. Creates a card the owner "
            "must confirm; nothing is published until they do.",
            {"draft_id": ID, "account_id": ID},
            Permission.SOCIAL_MANAGE,
            publish_post,
            module="ai_pro",
        ),
        Tool(
            "schedule_task",
            "Propose a task for later: once or repeating (daily, weekly on weekdays "
            "0=Monday..6=Sunday, monthly on a day 1-28), at a local HH:MM. "
            "kind agent_run: an instruction you will carry out then (read-only; whatever it "
            "proposes waits for approval). kind action: "
            "run action_tool (book_client, cancel_booking or bill_month) with action_args_json, "
            "the JSON arguments that tool takes, at that time. Use empty values for fields that "
            "do not apply (date '' unless once, weekdays [], day_of_month 0, instruction '' for "
            "an action, action_tool '' and action_args_json '' for agent_run). Creates a card "
            "the user must confirm.",
            {
                "kind": {"type": "string", "enum": ["agent_run", "action"]},
                "title": {"type": "string", "description": "Short name shown on the board"},
                "frequency": {"type": "string", "enum": ["once", "daily", "weekly", "monthly"]},
                "date": {"type": "string", "description": "YYYY-MM-DD for once, else empty"},
                "time": {"type": "string", "description": "Local HH:MM"},
                "weekdays": {"type": "array", "items": {"type": "integer"}},
                "day_of_month": {"type": "integer"},
                "instruction": {"type": "string"},
                "action_tool": {"type": "string"},
                "action_args_json": {"type": "string"},
            },
            Permission.AI_USE,
            schedule_task,
        ),
        Tool(
            "list_scheduled_tasks",
            "The user's scheduled tasks (active or paused) with their next run time.",
            {},
            Permission.AI_USE,
            list_scheduled_tasks,
        ),
        Tool(
            "cancel_scheduled_task",
            "Propose cancelling one of the user's scheduled tasks (id from list_scheduled_tasks). "
            "Creates a card the user must confirm.",
            {"task_id": ID},
            Permission.AI_USE,
            cancel_scheduled_task,
        ),
        Tool(
            "suggest_agent",
            "Offer the user a hand-over to a specialist on the team when their question is "
            "mostly that specialist's work. Only offers: the user decides.",
            {
                "agent_key": {"type": "string", "description": "The specialist's key"},
                "reason": {"type": "string", "description": "One sentence: why they fit"},
            },
            Permission.AI_USE,
            suggest_agent,
        ),
    )
}

# The toolbox domain of every tool: an agent only gets the tools of its domains. A new tool must
# be listed here (a test fails otherwise), so no tool reaches an agent by accident.
TOOL_DOMAINS: dict[str, str] = {
    "find_clients": "clients",
    "get_client": "clients",
    "inactive_members": "clients",
    "list_sessions": "schedule",
    "free_courts": "schedule",
    "get_session_roster": "bookings",
    "book_client": "bookings",
    "cancel_booking": "bookings",
    "get_metrics": "metrics",
    "client_sources": "sources",
    "lead_pipeline": "leads",
    "list_plans": "plans",
    "open_balances": "balances",
    "logged_time": "time",
    "log_time": "time",
    "billing_preview": "billing",
    "bill_month": "billing",
    "social_overview": "social",
    "top_posts": "social",
    "audience_summary": "social",
    "list_drafts": "content",
    "draft_post": "content",
    "publish_post": "social",
    "suggest_agent": "routing",
    "schedule_task": "tasks",
    "list_scheduled_tasks": "tasks",
    "cancel_scheduled_task": "tasks",
}

# Tools whose data has no branch to filter by (leads, for now). Whenever the conversation is
# narrowed to some branches (a branch-limited user, an agent or a chat with a scope), they are
# not offered, because their numbers would come from every branch.
BRANCH_BLIND: frozenset[str] = frozenset({"lead_pipeline"})


def _allowed(tool: Tool, permissions: frozenset[str], modules: set[str]) -> bool:
    return (
        tool.permission in permissions
        and (tool.module is None or tool.module in modules)
        and (tool.feature is None or tool.feature in modules)
    )


def tools_for(
    permissions: frozenset[str],
    modules: set[str],
    domains: frozenset[str] | None = None,
    narrowed: bool = False,
) -> list[Tool]:
    """Only the tools the user's permissions and the business's modules (and its industry's
    features, given in the same set) allow are offered; an agent narrows them to its domains,
    and a conversation kept to some branches drops the tools that cannot filter by branch."""
    return [
        tool
        for tool in TOOLS.values()
        if _allowed(tool, permissions, modules)
        and (domains is None or TOOL_DOMAINS[tool.name] in domains)
        and not (narrowed and tool.name in BRANCH_BLIND)
    ]


def run_tool(
    ctx: ToolContext, name: str, args: dict[str, Any], offered: frozenset[str] | None = None
) -> tuple[dict[str, Any], bool]:
    """Runs a tool for the model. Returns (result, is_error); never raises for tool errors.
    `offered` is the set of tool names this conversation was given: the model asking for any
    other tool is refused, even one the user could use elsewhere."""
    tool = TOOLS.get(name)
    if (
        tool is None
        or not _allowed(tool, ctx.tenant.permissions, ctx.modules)
        or (offered is not None and name not in offered)
    ):
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
