"""Read tools: they answer immediately."""

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.ai.scope import CLIENT_IN_SCOPE, visible_clients
from app.ai.tools.base import (
    MAX_ROSTER,
    MAX_ROWS,
    ToolContext,
    ToolError,
    _date,
    _local,
    _uuid,
)
from app.api import bookings as bookings_api
from app.api import freeze_requests as freeze_api
from app.api import plans as plans_api
from app.api import resources as resources_api
from app.api import schedule as schedule_api
from app.api import time_billing as time_api
from app.api.pagination import Page
from app.reports.metrics import METRICS, compute, members_at_risk, previous_period

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


def suggest_freeze(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """What a freeze of these days would do to each of the client's memberships. Only reads: the
    client asks for the freeze in the app, and a manager decides (round 7, R23)."""
    client_id = _uuid(args["client_id"], "client_id")
    starts_on, ends_on = (
        _date(args["start_date"], "start_date"),
        _date(args["end_date"], "end_date"),
    )
    if ends_on < starts_on or (ends_on - starts_on).days > 90:
        raise ToolError("the freeze must be 1 to 91 days, ending after it starts")
    db = ctx.tenant.session
    if not visible_clients(db, [client_id]):
        raise ToolError("no client with that id")
    rules = freeze_api.load_rules(db)
    today = freeze_api.local_today(db)
    options = []
    for e in plans_api.list_entitlements(db, client_id):
        if not e.freezable or e.state not in ("active", "upcoming"):
            continue
        preview = freeze_api.preview_for(db, e, rules, starts_on, ends_on)
        options.append(
            {
                "plan": e.name,
                "entitlement_id": str(e.id),
                "valid_until": e.ends_on.isoformat(),
                "would_end_on": preview.new_ends_on.isoformat(),
                "next_charge_moves": (
                    f"{preview.next_billing_from} to {preview.next_billing_to}"
                    if preview.next_billing_from
                    else None
                ),
                "credit_minor_units": preview.credit_amount,
                "fee_minor_units": preview.fee_amount,
                "would_be_refused_because": preview.problems,
            }
        )
    bank = freeze_api.bank_for(db, client_id, rules, starts_on.year)
    return {
        "note": "A suggestion only: nothing is frozen. The client asks for it in the app "
        "(Bookings, Freeze under the plan) and a manager decides. Never say it is done.",
        "today": today.isoformat(),
        "business_accepts_requests": rules.allow_requests,
        "days": (ends_on - starts_on).days + 1,
        "freeze_days_left_this_year": bank.remaining_days,
        "memberships": options,
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
