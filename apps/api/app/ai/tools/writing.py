"""Write tools: they never act, they propose a pending action the user confirms."""

import datetime as dt
import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from app.ai import scheduled
from app.ai.tools.base import (
    MAX_ROWS,
    ToolContext,
    ToolError,
    _date,
    _local,
    _uuid,
)
from app.ai.tools.reading import _billable_clients, _month_arg, get_client
from app.api import schedule as schedule_api
from app.core.brand import NAME


def payload_hash(tool_name: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": tool_name, "payload": payload}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _propose(
    ctx: ToolContext, tool_name: str, payload: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    if ctx.source is not None:
        preview = {**preview, "source": ctx.source}
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
    instruction = (
        "Nothing has happened yet. Tell the user to review and confirm the card shown under "
        "your message. Do not claim the action is done."
    )
    if ctx.source is not None:
        instruction = (
            f"Nothing has happened yet. The request now waits in {NAME}, under Settings, AI "
            "connections, where the business owner approves or rejects it. Tell the user to "
            "approve it there. Do not claim the action is done."
        )
    return {
        "pending_action_id": str(action_id),
        "status": "waiting_for_user_confirmation",
        "preview": preview,
        "instruction": instruction,
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
    from app.ai.tools import TOOLS  # the registry imports this module

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
