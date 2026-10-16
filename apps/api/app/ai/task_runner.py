"""Running the scheduled agent tasks that are due (round 5, A10).

`run_due_tasks` is a background job (app/jobs.py, called every few minutes by the keep-awake
workflow through POST /internal/jobs/tick, or by a worker once there is one). A task runs as the
user who approved it, with that user's permissions and branches as they are NOW, never as the
system: a member who left or lost AI access pauses the task, and an approved action is checked
again exactly like a confirmation (module, permission, unchanged payload).

Claiming is committed before anything runs: a task's next run time moves on first, so a crash or
a second tick can never run it twice. A failed run is retried once 15 minutes later; a repeating
task that fails three times in a row is paused."""

import datetime as dt
import json
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Connection, Engine, text
from sqlalchemy.orm import Session

from app.ai import actions, assistant, budget, scheduled
from app.ai.agents import CATALOG, find_agent, member_role_keys, state_of
from app.ai.gateway import LLMProvider, ProviderBusy, ProviderUnavailable, get_provider
from app.api.deps import ALL_BRANCH_ROLES, TenantContext, has_module, set_branch
from app.core.db import open_session, set_tenant
from app.core.permissions import Permission, effective_permissions

BATCH = 5  # tasks per tick: an agent run takes seconds and ticks come every few minutes
RETRY_AFTER = dt.timedelta(minutes=15)
MAX_FAILURES = 3


class Pause(Exception):
    """The task cannot run for a reason that needs a person; it is paused, not retried."""


class RunFailed(Exception):
    """The run failed; the message is stored on the run and shown on the board."""


def _claim(
    engine: Engine, now: dt.datetime, task_id: UUID | None = None, tenant_id: UUID | None = None
) -> list[dict[str, Any]]:
    """Takes the due tasks (or, for "run now", one named task): files a running record and moves
    the task on, all committed before anything runs."""
    claimed: list[dict[str, Any]] = []
    with engine.begin() as conn:
        if task_id is None:
            rows = conn.execute(
                text("""
                    SELECT * FROM app.ai_scheduled_tasks
                    WHERE status = 'active' AND next_run_at <= :now
                    ORDER BY next_run_at LIMIT :batch FOR UPDATE SKIP LOCKED
                """),
                {"now": now, "batch": BATCH},
            ).mappings()
        else:
            rows = conn.execute(
                text("""
                    SELECT * FROM app.ai_scheduled_tasks
                    WHERE id = :id AND tenant_id = :tenant AND status IN ('active', 'paused')
                    FOR UPDATE SKIP LOCKED
                """),
                {"id": task_id, "tenant": tenant_id},
            ).mappings()
        for task in [dict(r) for r in rows]:
            manual = task_id is not None
            late = None if manual else now - task["next_run_at"]
            once = task["schedule"]["type"] == "once"
            upcoming = (
                None if once else scheduled.next_run(task["schedule"], task["time_zone"], now)
            )
            if manual and not once:
                upcoming = task["next_run_at"]  # running now leaves the repeat as it was
            skipped = late is not None and late > scheduled.MAX_LATE
            run_id = conn.execute(
                text("""
                    INSERT INTO app.ai_task_runs (tenant_id, task_id, status, finished_at, result)
                    VALUES (:tenant, :task, :status, CASE WHEN :skip THEN now() END,
                            CASE WHEN :skip THEN CAST(:result AS jsonb) END)
                    RETURNING id
                """),
                {
                    "tenant": task["tenant_id"],
                    "task": task["id"],
                    "status": "skipped" if skipped else "running",
                    "skip": skipped,
                    "result": json.dumps({"error": "missed"}),
                },
            ).scalar_one()
            conn.execute(
                text("""
                    UPDATE app.ai_scheduled_tasks
                    SET next_run_at = CAST(:next AS timestamptz), last_run_at = :now,
                        updated_at = now(),
                        status = CASE WHEN CAST(:next AS timestamptz) IS NULL THEN 'done'
                                      ELSE status END
                    WHERE id = :id
                """),
                {"next": upcoming, "now": now, "id": task["id"]},
            )
            if not skipped:
                claimed.append(
                    {**task, "run_id": run_id, "manual": manual, "repeats": bool(upcoming)}
                )
    return claimed


def _context(db: Session, tenant_id: UUID, user_id: UUID) -> TenantContext:
    """The user's access today, as the request path builds it (see get_tenant_context)."""
    set_tenant(db, tenant_id)
    member = db.execute(
        text("""
            SELECT m.role, r.permissions AS custom_permissions, m.location_ids
            FROM app.tenant_members m
            LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
            WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = app.current_user_id()
        """)
    ).first()
    if member is None:
        raise Pause("member_gone")
    if db.execute(
        text("SELECT closed_at IS NOT NULL FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar():
        raise Pause("business_closed")
    permissions = effective_permissions(member.role, member.custom_permissions)
    if Permission.AI_USE not in permissions:
        raise Pause("permission_lost")
    if not has_module(db, "ai_basic", "ai_pro"):
        raise Pause("module_disabled")
    allowed = (
        frozenset(member.location_ids)
        if member.location_ids and member.role not in ALL_BRANCH_ROLES
        else None
    )
    set_branch(db, None, allowed)
    return TenantContext(db, tenant_id, member.role, permissions, allowed)


def _last_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message["role"] == "assistant":
            parts = [b["text"] for b in message["content"] if b.get("type") == "text"]
            if parts:
                return "\n".join(parts)
    return ""


def _agent_run(
    db: Session, ctx: TenantContext, task: dict[str, Any], provider: LLMProvider | None
) -> dict[str, Any]:
    user_id = task["created_by"]
    locale = db.execute(
        text("SELECT locale FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar()
    agent = find_agent(db, task["agent_key"], locale or "en")
    if agent is None or state_of(db, agent, member_role_keys(db, ctx.role))[0] != "active":
        raise Pause("agent_unavailable")
    if provider is None or getattr(provider, "model", None) == "demo":
        raise RunFailed("ai_not_configured")
    time_zone = task["time_zone"]
    month_start = dt.datetime.now(dt.UTC).astimezone(ZoneInfo(time_zone)).date().replace(day=1)
    if budget.over_limit(db, month_start):
        raise RunFailed("ai_limit_reached")
    if budget.over_person_limit(db, user_id, member_role_keys(db, ctx.role), month_start):
        raise RunFailed("ai_user_limit_reached")
    agent_id = None
    if task["agent_key"] not in CATALOG:
        agent_id = db.execute(
            text("SELECT id FROM app.ai_agents WHERE id::text = :raw"),
            {"raw": task["agent_key"].removeprefix("custom:")},
        ).scalar()
    conversation_id = db.execute(
        text("""
            INSERT INTO app.ai_conversations (tenant_id, user_id, agent_id, agent_key, title)
            VALUES (:t, :u, :agent_id, :agent, :title) RETURNING id
        """),
        {
            "t": task["tenant_id"],
            "u": user_id,
            "agent_id": agent_id,
            "agent": task["agent_key"],
            "title": task["title"][:80],
        },
    ).scalar_one()
    prompt = (
        "This is a scheduled task that runs by itself; nobody is reading along right now.\n"
        f"Task: {task['title']}\nInstruction: {task['instruction']}\n"
        "Use your read tools to do it. Anything that changes the business can only be proposed "
        "as a card and waits for the user to approve it later. Finish with a short report the "
        "user will read when they open this chat."
    )
    try:
        assistant.ask(
            provider, ctx, user_id, conversation_id, prompt, pending_ttl=scheduled.PENDING_TTL
        )
    except ProviderBusy as error:
        raise RunFailed("ai_busy") from error
    except ProviderUnavailable as error:
        raise RunFailed("ai_unavailable") from error
    messages = db.execute(
        text("SELECT messages FROM app.ai_conversations WHERE id = :id"), {"id": conversation_id}
    ).scalar_one()
    credits = float(
        db.execute(
            text("""
                SELECT coalesce(sum(quantity), 0) FROM app.usage_events
                WHERE meter = 'ai_credits' AND source_ref = :ref
            """),
            {"ref": f"ai_conversation:{conversation_id}"},
        ).scalar_one()
    )
    pending = [
        str(i)
        for i in db.execute(
            text(
                "SELECT id FROM app.pending_actions "
                "WHERE conversation_id = :id AND status = 'pending'"
            ),
            {"id": conversation_id},
        ).scalars()
    ]
    return {
        "result": {"summary": _last_text(messages)[:2000], "needs_approval": len(pending)},
        "conversation_id": conversation_id,
        "pending": pending,
        "credits": credits,
    }


def _run(engine: Engine, task: dict[str, Any], provider: LLMProvider | None) -> dict[str, Any]:
    """Runs one claimed task in its own transaction, as its creator."""
    db = open_session(engine, task["created_by"], task["tenant_id"])
    outcome: dict[str, Any] = {"status": "ok", "result": {}, "credits": 0.0, "pending": []}
    try:
        ctx = _context(db, task["tenant_id"], task["created_by"])
        if task["kind"] == "action":
            outcome["result"] = actions.run_approved(
                ctx,
                task["created_by"],
                task["tool_name"],
                task["payload"],
                task["payload_hash"],
                task["id"],
            )
        else:
            outcome.update(_agent_run(db, ctx, task, provider))
        db.commit()
    except Pause as pause:
        db.rollback()
        outcome = {"status": "skipped", "result": {"error": str(pause)}, "pause": str(pause)}
    except RunFailed as error:
        db.rollback()
        outcome = {"status": "failed", "result": {"error": str(error)}}
    except HTTPException as error:
        db.rollback()
        outcome = {"status": "failed", "result": {"error": str(error.detail)}}
    except Exception as error:  # a bug or an outage must not stop the other tasks
        db.rollback()
        outcome = {"status": "failed", "result": {"error": type(error).__name__}}
    finally:
        db.close()
    return outcome


def _finish(
    engine: Engine, task: dict[str, Any], outcome: dict[str, Any], now: dt.datetime
) -> None:
    status = outcome["status"]
    credits = outcome.get("credits", 0.0)
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE app.ai_task_runs
                SET finished_at = now(), status = :status, credits = :credits,
                    result = CAST(:result AS jsonb), conversation_id = :conversation,
                    pending_action_ids = CAST(:pending AS uuid[])
                WHERE id = :id
            """),
            {
                "status": status,
                "credits": credits,
                "result": json.dumps(outcome["result"], default=str),
                "conversation": outcome.get("conversation_id"),
                "pending": "{" + ",".join(outcome.get("pending", [])) + "}",
                "id": task["run_id"],
            },
        )
        if pause := outcome.get("pause"):
            conn.execute(
                text("""
                    UPDATE app.ai_scheduled_tasks
                    SET status = 'paused', status_reason = :reason, updated_at = now()
                    WHERE id = :id
                """),
                {"reason": pause, "id": task["id"]},
            )
            return
        if status == "ok":
            over = credits > task["max_credits"]
            conn.execute(
                text("""
                    UPDATE app.ai_scheduled_tasks
                    SET failures = 0, updated_at = now(),
                        status = CASE WHEN :over AND status = 'active' THEN 'paused'
                                      ELSE status END,
                        status_reason = CASE WHEN :over THEN 'over_credit_cap' END
                    WHERE id = :id
                """),
                {"over": over, "id": task["id"]},
            )
            return
        failures = task["failures"] + 1
        if task["manual"]:
            conn.execute(
                text("UPDATE app.ai_scheduled_tasks SET failures = :n WHERE id = :id"),
                {"n": failures, "id": task["id"]},
            )
            return
        retry_at = now + RETRY_AFTER
        if task["repeats"]:
            # Retry once soon; the third failure in a row pauses the task.
            conn.execute(
                text("""
                    UPDATE app.ai_scheduled_tasks
                    SET failures = :n, updated_at = now(),
                        next_run_at = CASE
                            WHEN :n = 1 THEN least(next_run_at, CAST(:retry AS timestamptz))
                            ELSE next_run_at END,
                        status = CASE WHEN :n >= :max THEN 'paused' ELSE status END,
                        status_reason = CASE WHEN :n >= :max THEN 'failed_3_times' END
                    WHERE id = :id
                """),
                {"n": failures, "retry": retry_at, "max": MAX_FAILURES, "id": task["id"]},
            )
        else:
            conn.execute(
                text("""
                    UPDATE app.ai_scheduled_tasks
                    SET failures = CAST(:n AS integer), updated_at = now(),
                        status = CASE WHEN :n = 1 THEN 'active' ELSE 'failed' END,
                        next_run_at = CASE WHEN :n = 1 THEN CAST(:retry AS timestamptz) END,
                        status_reason = CASE WHEN :n = 1 THEN NULL ELSE 'run_failed' END
                    WHERE id = :id
                """),
                {"n": failures, "retry": retry_at, "id": task["id"]},
            )


def run_claimed(
    engine: Engine, tasks: list[dict[str, Any]], provider: LLMProvider | None, now: dt.datetime
) -> dict[str, int]:
    counts = {"ok": 0, "failed": 0, "skipped": 0}
    for task in tasks:
        outcome = _run(engine, task, provider)
        _finish(engine, task, outcome, now)
        counts[outcome["status"]] += 1
    return counts


def run_due_tasks(
    conn: Connection, provider: LLMProvider | None = None, now: dt.datetime | None = None
) -> dict[str, int]:
    """The background job: runs every task whose time has come (a batch per call)."""
    now = now or dt.datetime.now(dt.UTC)
    provider = provider if provider is not None else get_provider()
    return run_claimed(conn.engine, _claim(conn.engine, now), provider, now)


def run_now(
    engine: Engine, tenant_id: UUID, task_id: UUID, provider: LLMProvider | None
) -> dict[str, int]:
    """ "Run now" from the board: one task, right away, without moving its schedule."""
    now = dt.datetime.now(dt.UTC)
    return run_claimed(engine, _claim(engine, now, task_id, tenant_id), provider, now)
