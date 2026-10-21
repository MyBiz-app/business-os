"""Proactive agent behaviours (round 5, A8): the morning briefing and opt-in suggestions.

Both are ordinary scheduled tasks (app/ai/scheduled.py) that the system files for a person who
switched the behaviour on. So everything a scheduled run already guarantees applies unchanged: it
runs as that person with their permissions and branches as they are now, counts against the plan's
task limit and the AI credit caps, is read-only, and anything it wants to change is a card that
waits for the person's approval."""

import datetime as dt
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import scheduled

BRIEFING = "morning_briefing"
SUGGESTIONS = "suggestions"
KEYS: tuple[str, ...] = (BRIEFING, SUGGESTIONS)

AGENT = "chief"
DEFAULT_TIME = {BRIEFING: "07:30", SUGGESTIONS: "08:00"}
SUNDAY = 6
# Suggestions can cost a few more tool calls than a summary, so they get a slightly bigger cap.
MAX_CREDITS = {BRIEFING: 10, SUGGESTIONS: 15}
TITLES = {BRIEFING: "Morning briefing", SUGGESTIONS: "Weekly suggestions"}

_LANGUAGES = {"he": "Hebrew", "en": "English"}

_INSTRUCTIONS = {
    BRIEFING: (
        "Write today's morning briefing for the person who will read this. Use your read tools "
        "and cover, briefly and in this order: today's appointments and sessions (times, names, "
        "how full they are), new or waiting leads, and open items that need attention (cards "
        "waiting for approval, unpaid or overdue amounts, birthdays or expiring memberships when "
        "you can see them). Skip a section that has nothing in it. Keep it under 150 words and "
        "end with the single most important thing to do first. Do not propose any change."
    ),
    SUGGESTIONS: (
        "Look at the business for chances worth acting on this week: clients who stopped coming, "
        "sessions that are far from full, leads nobody followed up, an unusual drop or rise in "
        "revenue. If a city has many new leads, a high conversion and no branch (map_areas), say "
        "so as a chance to look at. If the context shows the business has no website and many "
        "recent leads came from Instagram or other social networks, one suggestion may be to order "
        "a website from My website (/website), so those leads have somewhere to land. Use your "
        "read tools. "
        "Report at most three suggestions, each one line with the "
        "reason. For a suggestion you can act on with a tool, prepare it as a card so the person "
        "can approve it, and never act without a card. If there is nothing worth suggesting, say "
        "so in one line."
    ),
}


def instruction(key: str, locale: str) -> str:
    language = _LANGUAGES.get(locale, "English")
    return f"{_INSTRUCTIONS[key]} Write the whole report in {language}."


def schedule_for(key: str, time: str, weekday: int | None) -> dict[str, Any]:
    if key == BRIEFING:
        return scheduled.build_schedule("daily", time)
    return scheduled.build_schedule(
        "weekly", time, weekdays=[SUNDAY if weekday is None else weekday]
    )


def get(db: Session, user_id: UUID, key: str) -> dict[str, Any] | None:
    row = (
        db.execute(
            text("""
                SELECT id, status, status_reason, schedule, next_run_at, last_run_at
                FROM app.ai_scheduled_tasks WHERE created_by = :user AND system_key = :key
            """),
            {"user": user_id, "key": key},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def enable(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    key: str,
    time: str,
    weekday: int | None,
    modules: list[str],
) -> None:
    """Switches the behaviour on (or moves it to a new time). Raises ScheduleError when the time
    is invalid or the plan's task limit is used up."""
    schedule = schedule_for(key, time, weekday)
    row = get(db, user_id, key)
    if row is None:
        scheduled.check_limit(db, modules)
    locale, time_zone = db.execute(
        text("SELECT locale, time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).one()
    upcoming = scheduled.next_run(schedule, time_zone, dt.datetime.now(dt.UTC))
    params = {
        "tenant": tenant_id,
        "user": user_id,
        "key": key,
        "agent": AGENT,
        "title": TITLES[key],
        "instruction": instruction(key, locale or "en"),
        "schedule": json.dumps(schedule),
        "time_zone": time_zone,
        "next": upcoming,
        "credits": MAX_CREDITS[key],
    }
    db.execute(
        text("""
            INSERT INTO app.ai_scheduled_tasks
                (tenant_id, created_by, agent_key, kind, title, instruction, schedule,
                 time_zone, next_run_at, max_credits, system_key)
            VALUES (:tenant, :user, :agent, 'agent_run', :title, :instruction,
                    CAST(:schedule AS jsonb), :time_zone, :next, :credits, :key)
            ON CONFLICT (tenant_id, created_by, system_key) WHERE system_key IS NOT NULL
            DO UPDATE SET schedule = EXCLUDED.schedule, next_run_at = EXCLUDED.next_run_at,
                          instruction = EXCLUDED.instruction, time_zone = EXCLUDED.time_zone,
                          status = 'active', status_reason = NULL, failures = 0,
                          updated_at = now()
        """),
        params,
    )


def disable(db: Session, user_id: UUID, key: str) -> None:
    """Switches it off; the task and its history stay, so switching on again keeps both."""
    db.execute(
        text("""
            UPDATE app.ai_scheduled_tasks
            SET status = 'paused', status_reason = NULL, updated_at = now()
            WHERE created_by = :user AND system_key = :key
        """),
        {"user": user_id, "key": key},
    )
