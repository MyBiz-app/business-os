"""The scheduled-tasks board of the AI team: what the agents will do later, when, and how the
earlier runs went.

A task is created by an agent in a chat, through a card the user confirms (see
`schedule_task` in app/ai/tools/); here the owner of a task pauses, resumes, edits the time,
deletes or runs it. Whoever may manage the AI team (`ai.manage`) also sees and can pause or
delete everybody's tasks. A task always runs as the person who created it."""

import datetime as dt
import json
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.ai import proactive, scheduled, task_runner
from app.api.assistant import ProviderDep, _check_budget, _check_user_rate, require_ai
from app.api.common import not_found
from app.api.deps import TenantContext, UserDep
from app.core.db import EngineDep
from app.core.permissions import Permission

router = APIRouter(prefix="/ai/tasks", tags=["ai"])

AIDep = Annotated[TenantContext, Depends(require_ai)]


class ScheduleBody(BaseModel):
    frequency: Literal["once", "daily", "weekly", "monthly"]
    time: str = Field(description="Local HH:MM")
    date: str | None = Field(default=None, description="YYYY-MM-DD, for once")
    weekdays: list[int] | None = Field(default=None, description="0 = Monday .. 6 = Sunday")
    day_of_month: int | None = Field(default=None, description="1-28, for monthly")


class TaskCard(BaseModel):
    id: UUID
    title: str
    kind: Literal["action", "agent_run"]
    agent_key: str
    status: Literal["active", "paused", "done", "failed"]
    status_reason: str | None
    schedule: dict[str, Any]
    time_zone: str
    next_run_at: dt.datetime | None
    last_run_at: dt.datetime | None
    max_credits: int
    instruction: str | None
    preview: dict[str, Any] | None
    mine: bool
    # Set for the morning briefing and the suggestions, which the system files (A8).
    system_key: Literal["morning_briefing", "suggestions"] | None
    # The last run's outcome, and how many of its cards still wait for approval.
    last_status: Literal["running", "ok", "failed", "skipped"] | None
    last_error: str | None
    waiting_for_approval: int


class Tasks(BaseModel):
    tasks: list[TaskCard]
    active: int
    limit: int
    # False until a worker runs the tasks every minute: the board says "around" the set time.
    precise_timing: bool = False


class RunCard(BaseModel):
    id: int
    started_at: dt.datetime
    finished_at: dt.datetime | None
    status: Literal["running", "ok", "failed", "skipped"]
    credits: float
    summary: str | None
    error: str | None
    conversation_id: UUID | None
    pending_action_ids: list[UUID]


class TaskUpdate(BaseModel):
    status: Literal["active", "paused"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    instruction: str | None = Field(default=None, min_length=1, max_length=2000)
    schedule: ScheduleBody | None = None


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _can_manage(context: TenantContext) -> bool:
    return Permission.AI_MANAGE in context.permissions


def _modules(context: TenantContext) -> list[str]:
    return list(
        context.session.execute(text("SELECT module_key FROM app.tenant_modules")).scalars()
    )


CARD_SQL = """
    SELECT t.*, t.created_by = :user AS mine,
           r.status AS last_status, r.result ->> 'error' AS last_error,
           coalesce((SELECT count(*) FROM app.pending_actions p
                     WHERE p.id = ANY(r.pending_action_ids) AND p.status = 'pending'), 0)
               AS waiting_for_approval
    FROM app.ai_scheduled_tasks t
    LEFT JOIN LATERAL (
        SELECT status, result, pending_action_ids FROM app.ai_task_runs
        WHERE task_id = t.id ORDER BY started_at DESC, id DESC LIMIT 1
    ) r ON true
"""


@router.get("")
def list_tasks(context: AIDep, user: UserDep) -> Tasks:
    rows = (
        context.session.execute(
            text(
                CARD_SQL
                + """
                WHERE (t.created_by = :user OR :everyone)
                  AND (t.status IN ('active', 'paused', 'failed')
                       OR t.last_run_at > now() - interval '30 days')
                ORDER BY (t.status = 'active') DESC, t.next_run_at NULLS LAST, t.created_at DESC
                LIMIT 200
                """
            ),
            {"user": user.id, "everyone": _can_manage(context)},
        )
        .mappings()
        .all()
    )
    live = [r for r in rows if r["status"] in ("active", "paused")]
    return Tasks(
        tasks=[TaskCard.model_validate(dict(r)) for r in rows],
        active=len(live),
        limit=scheduled.active_limit(_modules(context)),
    )


def _task(context: TenantContext, task_id: UUID, user_id: UUID, own_only: bool) -> dict[str, Any]:
    row = (
        context.session.execute(
            text(CARD_SQL + " WHERE t.id = :id FOR UPDATE OF t"),
            {"id": task_id, "user": user_id},
        )
        .mappings()
        .first()
    )
    if row is None or (not row["mine"] and (own_only or not _can_manage(context))):
        raise not_found()
    return dict(row)


@router.get("/{task_id}/runs")
def list_runs(task_id: UUID, context: AIDep, user: UserDep) -> list[RunCard]:
    _task(context, task_id, user.id, own_only=False)
    rows = context.session.execute(
        text("""
            SELECT id, started_at, finished_at, status, credits::float AS credits,
                   result ->> 'summary' AS summary, result ->> 'error' AS error,
                   conversation_id, pending_action_ids
            FROM app.ai_task_runs WHERE task_id = :id
            ORDER BY started_at DESC, id DESC LIMIT 20
        """),
        {"id": task_id},
    ).mappings()
    return [RunCard.model_validate(dict(r)) for r in rows]


@router.patch("/{task_id}")
def update_task(task_id: UUID, body: TaskUpdate, context: AIDep, user: UserDep) -> TaskCard:
    db = context.session
    task = _task(context, task_id, user.id, own_only=False)
    if task["status"] == "done":
        raise _bad("task_finished")
    edits_content = body.title or body.instruction or body.schedule
    if edits_content and not task["mine"]:
        raise not_found()  # others may pause or delete a task, not rewrite it
    if body.instruction and task["kind"] != "agent_run":
        raise _bad("instruction_only_for_agent_runs")  # an approved action is never rewritten
    schedule = task["schedule"]
    if body.schedule:
        try:
            schedule = scheduled.build_schedule(**body.schedule.model_dump())
        except scheduled.ScheduleError as error:
            raise _bad(str(error)) from error
    new_status = body.status or task["status"]
    next_run = task["next_run_at"]
    if new_status == "active" and (body.status == "active" or body.schedule):
        # Resuming (or moving) restarts the clock from now.
        next_run = scheduled.next_run(schedule, task["time_zone"], dt.datetime.now(dt.UTC))
        if next_run is None:
            raise _bad("time_passed")
    db.execute(
        text("""
            UPDATE app.ai_scheduled_tasks
            SET title = coalesce(:title, title), instruction = coalesce(:instruction, instruction),
                schedule = CAST(:schedule AS jsonb), status = :status, next_run_at = :next,
                failures = CASE WHEN :status = 'active' AND status <> 'active' THEN 0
                                ELSE failures END,
                status_reason = CASE WHEN :status = 'active' THEN NULL ELSE status_reason END,
                updated_at = now()
            WHERE id = :id
        """),
        {
            "title": body.title,
            "instruction": body.instruction,
            "schedule": json.dumps(schedule),
            "status": new_status,
            "next": next_run if new_status == "active" else task["next_run_at"],
            "id": task_id,
        },
    )
    return TaskCard.model_validate(_task(context, task_id, user.id, own_only=False))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, context: AIDep, user: UserDep) -> None:
    _task(context, task_id, user.id, own_only=False)
    context.session.execute(
        text("DELETE FROM app.ai_scheduled_tasks WHERE id = :id"), {"id": task_id}
    )


@router.post("/{task_id}/run")
def run_task_now(
    task_id: UUID, context: AIDep, user: UserDep, provider: ProviderDep, engine: EngineDep
) -> RunCard:
    """Runs the task right away, as its owner, without moving its schedule."""
    task = _task(context, task_id, user.id, own_only=True)
    if task["status"] not in ("active", "paused"):
        raise _bad("task_finished")
    if task["kind"] == "agent_run":
        if provider is None:
            raise HTTPException(status_code=503, detail="ai_not_configured")
        _check_budget(context, user.id, provider)
        _check_user_rate(user.id, provider)
    context.session.commit()  # release the row lock: the runner works in its own transaction
    task_runner.run_now(engine, context.tenant_id, task_id, provider)
    latest = list_runs(task_id, context, user)
    if not latest:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="busy")
    return latest[0]


ProactiveKey = Literal["morning_briefing", "suggestions"]


class ProactiveSetting(BaseModel):
    key: ProactiveKey
    enabled: bool
    time: str
    weekday: int | None = Field(description="Suggestions only: 0 = Monday .. 6 = Sunday")
    # Why the system paused it (e.g. permission_lost); None when it was switched off by the person.
    paused_reason: str | None
    next_run_at: dt.datetime | None
    last_run_at: dt.datetime | None
    agent_key: str


class Proactive(BaseModel):
    settings: list[ProactiveSetting]
    can_manage: bool


class ProactiveBody(BaseModel):
    enabled: bool
    time: str | None = Field(default=None, description="Local HH:MM")
    weekday: int | None = Field(default=None, ge=0, le=6)


def _setting(db: Any, user_id: UUID, key: str) -> ProactiveSetting:
    row = proactive.get(db, user_id, key)
    schedule = row["schedule"] if row else None
    return ProactiveSetting(
        key=key,  # type: ignore[arg-type]
        enabled=bool(row and row["status"] == "active"),
        time=schedule["time"] if schedule else proactive.DEFAULT_TIME[key],
        weekday=((schedule or {}).get("weekdays") or [proactive.SUNDAY])[0]
        if key == proactive.SUGGESTIONS
        else None,
        paused_reason=row["status_reason"] if row and row["status"] == "paused" else None,
        next_run_at=row["next_run_at"] if row and row["status"] == "active" else None,
        last_run_at=row["last_run_at"] if row else None,
        agent_key=proactive.AGENT,
    )


@router.get("/proactive")
def get_proactive(context: AIDep, user: UserDep) -> Proactive:
    """The person's own proactive behaviours: what is on and at what time."""
    return Proactive(
        settings=[_setting(context.session, user.id, key) for key in proactive.KEYS],
        can_manage=_can_manage(context),
    )


@router.put("/proactive/{key}")
def set_proactive(
    key: ProactiveKey, body: ProactiveBody, context: AIDep, user: UserDep
) -> Proactive:
    """Switches the morning briefing or the weekly suggestions on or off, or moves the time. They
    run as the person who switches them on, so they never see more than that person can."""
    if not _can_manage(context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    db = context.session
    if body.enabled:
        existing = proactive.get(db, user.id, key)
        time = body.time or (existing["schedule"]["time"] if existing else None)
        weekday = body.weekday
        if weekday is None and existing and key == proactive.SUGGESTIONS:
            weekday = existing["schedule"]["weekdays"][0]
        try:
            proactive.enable(
                db,
                context.tenant_id,
                user.id,
                key,
                time or proactive.DEFAULT_TIME[key],
                weekday,
                _modules(context),
            )
        except scheduled.ScheduleError as error:
            raise _bad(str(error)) from error
    else:
        proactive.disable(db, user.id, key)
    return get_proactive(context, user)
