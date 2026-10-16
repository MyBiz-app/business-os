"""Scheduled agent tasks: the schedule rules, the limits and creating a task.

A task runs later, once or on a repeat, as the user who approved it (see app/ai/task_runner.py).
Times are kept in the business's time zone: "every Sunday at 08:00" stays at 08:00 across the
clock change, and `next_run_at` is the matching UTC instant."""

import datetime as dt
import json
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

Frequency = Literal["once", "daily", "weekly", "monthly"]
FREQUENCIES: tuple[str, ...] = ("once", "daily", "weekly", "monthly")
KINDS: tuple[str, ...] = ("action", "agent_run")

# The write tools a task may run later: the ones that act on one booking, entry or bill run.
SCHEDULABLE_TOOLS: frozenset[str] = frozenset({"book_client", "cancel_booking", "bill_month"})

MAX_ACTIVE = {"ai_basic": 10, "ai_pro": 50}
DEFAULT_MAX_CREDITS = 20
# A scheduled run that is found more than this late (the server was down) is skipped, not run.
MAX_LATE = dt.timedelta(hours=24)
# What a proposal made during an unattended run waits for the user.
PENDING_TTL = dt.timedelta(days=3)


class ScheduleError(ValueError):
    """The schedule asked for is not valid (the message is for the user or the model)."""


def _time(value: Any) -> tuple[int, int]:
    try:
        parsed = dt.time.fromisoformat(str(value))
    except ValueError as error:
        raise ScheduleError("time must be HH:MM, local time") from error
    return parsed.hour, parsed.minute


def build_schedule(
    frequency: str,
    time: str,
    date: str | None = None,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
) -> dict[str, Any]:
    """A normalised schedule. `weekdays` count from Monday = 0; `day_of_month` is 1-28."""
    if frequency not in FREQUENCIES:
        raise ScheduleError("frequency must be once, daily, weekly or monthly")
    hour, minute = _time(time)
    schedule: dict[str, Any] = {"type": frequency, "time": f"{hour:02d}:{minute:02d}"}
    if frequency == "once":
        try:
            schedule["date"] = dt.date.fromisoformat(str(date)).isoformat()
        except ValueError as error:
            raise ScheduleError("a one-time task needs a date like 2026-10-18") from error
    elif frequency == "weekly":
        days = sorted(set(weekdays or []))
        if not days or any(not isinstance(d, int) or not 0 <= d <= 6 for d in days):
            raise ScheduleError("weekly needs weekdays, numbers from 0 (Monday) to 6 (Sunday)")
        schedule["weekdays"] = days
    elif frequency == "monthly":
        if not isinstance(day_of_month, int) or not 1 <= day_of_month <= 28:
            raise ScheduleError("monthly needs a day of the month from 1 to 28")
        schedule["day"] = day_of_month
    return schedule


def next_run(schedule: dict[str, Any], time_zone: str, after: dt.datetime) -> dt.datetime | None:
    """The first run strictly after `after` (UTC), or None when a one-time task has passed."""
    zone = ZoneInfo(time_zone)
    hour, minute = _time(schedule["time"])
    kind = schedule["type"]

    def at(day: dt.date) -> dt.datetime:
        return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=zone)

    if kind == "once":
        moment = at(dt.date.fromisoformat(schedule["date"]))
        return moment.astimezone(dt.UTC) if moment > after else None
    first_day = after.astimezone(zone).date()
    for offset in range(63):
        day = first_day + dt.timedelta(days=offset)
        if kind == "weekly" and day.weekday() not in schedule["weekdays"]:
            continue
        if kind == "monthly" and day.day != schedule["day"]:
            continue
        moment = at(day)
        if moment > after:
            return moment.astimezone(dt.UTC)
    return None


def active_limit(modules: set[str] | list[str]) -> int:
    return max((MAX_ACTIVE[key] for key in MAX_ACTIVE if key in modules), default=0)


def check_limit(db: Session, modules: set[str] | list[str]) -> None:
    """Raises ScheduleError when the business already has as many live tasks as its AI module
    allows (10 on AI Basic, 50 on AI Pro)."""
    limit = active_limit(modules)
    live = db.execute(
        text("SELECT count(*) FROM app.ai_scheduled_tasks WHERE status IN ('active', 'paused')")
    ).scalar_one()
    if live >= limit:
        raise ScheduleError(f"the business already has {live} scheduled tasks, the most it allows")


def create_task(
    db: Session, tenant_id: UUID, user_id: UUID, agent_key: str, spec: dict[str, Any]
) -> UUID:
    """Files an approved task. `spec` is the payload of the confirmed card."""
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    first = next_run(spec["schedule"], time_zone, dt.datetime.now(dt.UTC))
    if first is None:
        raise ScheduleError("that time has already passed")
    action = spec["kind"] == "action"
    return db.execute(
        text("""
            INSERT INTO app.ai_scheduled_tasks
                (tenant_id, created_by, agent_key, kind, title, tool_name, payload, payload_hash,
                 preview, instruction, schedule, time_zone, next_run_at, max_credits)
            VALUES (:tenant_id, :user_id, :agent, :kind, :title, :tool, CAST(:payload AS jsonb),
                    :hash, CAST(:preview AS jsonb), :instruction, CAST(:schedule AS jsonb),
                    :time_zone, :next_run, :max_credits)
            RETURNING id
        """),
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "agent": agent_key,
            "kind": spec["kind"],
            "title": spec["title"],
            "tool": spec["tool_name"] if action else None,
            "payload": json.dumps(spec["payload"]) if action else None,
            "hash": spec["payload_hash"] if action else None,
            "preview": json.dumps(spec["preview"]) if action else None,
            "instruction": None if action else spec["instruction"],
            "schedule": json.dumps(spec["schedule"]),
            "time_zone": time_zone,
            "next_run": first,
            "max_credits": spec.get("max_credits", DEFAULT_MAX_CREDITS),
        },
    ).scalar_one()
