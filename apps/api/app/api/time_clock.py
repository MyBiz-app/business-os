"""Time clock (round 6, P2): people clock in and out, managers see and fix the month.

- A person clocks in and out themselves (`/me/time-clock`). Clocking in links the entry to the
  shift they are planned for, when there is one.
- A manager with `time.approve` sees the month per person (planned against worked, missing
  shifts, overtime by rate), adds or corrects an entry with a written reason (also written to the
  audit log), and approves the month. An approved month is locked until it is reopened.
- The overtime rules are data (`time_clock_rules`); the arithmetic is `app.schedule.time_clock`."""

import datetime as dt
import json
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, UserDep, ensure_branch_allowed, require
from app.api.staff import _ensure_member_in_reach
from app.core.permissions import Permission
from app.schedule.time_clock import Breakdown, ClockRules, compute, split_by_day

router = APIRouter(tags=["time-clock"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ApproveDep = Annotated[TenantContext, Depends(require(Permission.TIME_APPROVE))]
SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

# A shift counts as "the one being worked" from this long before it starts until it ends.
EARLY_CLOCK_IN = dt.timedelta(hours=2)
MAX_OPEN = dt.timedelta(hours=24)


class Rules(BaseModel):
    work_days_per_week: Literal[5, 6] = 5
    week_hours: float = Field(default=42, gt=0, le=100)
    day_hours_5: float = Field(default=8.6, gt=0, le=24)
    day_hours_6: float = Field(default=8, gt=0, le=24)
    tier1_hours: float = Field(default=2, ge=0, le=24)
    tier1_percent: int = Field(default=125, ge=100, le=300)
    tier2_percent: int = Field(default=150, ge=100, le=300)
    rest_day_percent: int = Field(default=150, ge=100, le=300)
    rest_weekday: int = Field(default=5, ge=0, le=6, description="0 = Monday, 5 = Saturday")


class Hours(BaseModel):
    """Hours worked, by pay rate (see `app.schedule.time_clock.Breakdown`)."""

    total: float = 0
    regular: float = 0
    tier1: float = 0
    tier2: float = 0
    rest_day: float = 0
    weighted: float = 0


class Entry(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    location_id: UUID
    location_name: str
    shift_id: UUID | None
    clock_in: dt.datetime
    clock_out: dt.datetime | None
    source: Literal["clock", "manual"]
    correction_reason: str | None
    corrected_by_name: str | None


class PlannedShift(BaseModel):
    id: UUID
    location_id: UUID
    location_name: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    position: str | None


class ClockState(BaseModel):
    """What the clock screen shows: the open entry (if clocked in), the shift planned around now
    and this week's entries."""

    open_entry: Entry | None
    planned_shift: PlannedShift | None
    recent: list[Entry]


class ClockIn(BaseModel):
    location_id: UUID | None = Field(
        default=None, description="Defaults to the planned shift's branch, else the only branch"
    )


class PersonMonth(BaseModel):
    user_id: UUID
    user_name: str
    planned_hours: float
    worked: Hours
    missing_shifts: int = Field(description="Past shifts with no clocked time")
    open_entries: int
    corrections: int
    approved: bool
    approved_at: dt.datetime | None


class Month(BaseModel):
    month: dt.date
    people: list[PersonMonth]


class PersonDetail(BaseModel):
    month: dt.date
    user_id: UUID
    user_name: str
    approved: bool
    planned_hours: float
    worked: Hours
    days: dict[dt.date, float]
    entries: list[Entry]


class EntryCreate(BaseModel):
    user_id: UUID
    location_id: UUID
    clock_in: dt.datetime
    clock_out: dt.datetime
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def ordered(self) -> "EntryCreate":
        if self.clock_in.tzinfo is None or self.clock_out.tzinfo is None:
            raise ValueError("times need a time zone")
        if not self.clock_in < self.clock_out <= self.clock_in + MAX_OPEN:
            raise ValueError("clock_out must be after clock_in, within 24 hours")
        return self


class EntryCorrection(BaseModel):
    clock_in: dt.datetime | None = None
    clock_out: dt.datetime | None = None
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def aware(self) -> "EntryCorrection":
        for value in (self.clock_in, self.clock_out):
            if value is not None and value.tzinfo is None:
                raise ValueError("times need a time zone")
        return self


ENTRY_SELECT = """
    SELECT e.id, e.user_id, coalesce(u.full_name, u.email) AS user_name, e.location_id,
           l.name AS location_name, e.shift_id, e.clock_in, e.clock_out, e.source,
           e.correction_reason, coalesce(c.full_name, c.email) AS corrected_by_name
    FROM app.time_clock_entries e
    JOIN app.users u ON u.id = e.user_id
    JOIN app.locations l ON l.tenant_id = e.tenant_id AND l.id = e.location_id
    LEFT JOIN app.users c ON c.id = e.corrected_by
"""


def _entry(session: Session, entry_id: UUID) -> Entry:
    row = (
        session.execute(
            text(f"{ENTRY_SELECT} WHERE e.id = :id AND app.in_branch(e.location_id)"),
            {"id": entry_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Entry.model_validate(dict(row))


def _time_zone(session: Session) -> str:
    return session.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()


def load_rules(session: Session) -> Rules:
    row = (
        session.execute(
            text("""
                SELECT work_days_per_week, week_hours::float, day_hours_5::float,
                       day_hours_6::float, tier1_hours::float, tier1_percent, tier2_percent,
                       rest_day_percent, rest_weekday
                FROM app.time_clock_rules WHERE tenant_id = app.current_tenant_id()
            """)
        )
        .mappings()
        .first()
    )
    return Rules.model_validate(dict(row)) if row else Rules()


def _clock_rules(rules: Rules) -> ClockRules:
    return ClockRules(**rules.model_dump())


def _hours(breakdown: Breakdown) -> Hours:
    return Hours(
        total=breakdown.total,
        regular=breakdown.regular,
        tier1=breakdown.tier1,
        tier2=breakdown.tier2,
        rest_day=breakdown.rest_day,
        weighted=breakdown.weighted,
    )


def _audit(session: Session, action: str, entry_id: UUID, details: dict[str, object]) -> None:
    session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (app.current_tenant_id(), 'user', app.current_user_id(), :action,
                    'time_clock_entry', :entity_id, CAST(:details AS jsonb))
        """),
        {"action": action, "entity_id": entry_id, "details": json.dumps(details, default=str)},
    )


def _month_bounds(month: dt.date, time_zone: str) -> tuple[dt.datetime, dt.datetime]:
    """The month as two instants, in the business's time zone."""
    zone = ZoneInfo(time_zone)
    start = dt.datetime.combine(month, dt.time.min, tzinfo=zone)
    following = (month + dt.timedelta(days=32)).replace(day=1)
    return start, dt.datetime.combine(following, dt.time.min, tzinfo=zone)


def _month_of(instant: dt.datetime, time_zone: str) -> dt.date:
    return instant.astimezone(ZoneInfo(time_zone)).date().replace(day=1)


def _ensure_month_open(session: Session, user_id: UUID, months: set[dt.date]) -> None:
    locked = session.execute(
        text("""
            SELECT 1 FROM app.time_clock_approvals
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
              AND month = ANY(:months)
        """),
        {"user_id": user_id, "months": list(months)},
    ).first()
    if locked is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="month_approved")


def _planned_shift(session: Session, user_id: UUID, now: dt.datetime) -> PlannedShift | None:
    """The shift the person is working now or about to (it starts within `EARLY_CLOCK_IN`), the
    nearest to its start first."""
    row = (
        session.execute(
            text("""
                SELECT s.id, s.location_id, l.name AS location_name, s.starts_at, s.ends_at,
                       s.position
                FROM app.shifts s
                JOIN app.locations l ON l.tenant_id = s.tenant_id AND l.id = s.location_id
                WHERE s.tenant_id = app.current_tenant_id() AND s.user_id = :user_id
                  AND s.starts_at - :early <= :now AND s.ends_at > :now
                ORDER BY abs(extract(epoch FROM s.starts_at - :now))
                LIMIT 1
            """),
            {"user_id": user_id, "now": now, "early": EARLY_CLOCK_IN},
        )
        .mappings()
        .first()
    )
    return PlannedShift.model_validate(dict(row)) if row else None


# -- the person's own clock ------------------------------------------------------------------


@router.get("/me/time-clock")
def my_clock(user: UserDep, context: ReadDep) -> ClockState:
    db = context.session
    now = dt.datetime.now(dt.UTC)
    rows = (
        db.execute(
            text(f"""
                {ENTRY_SELECT}
                WHERE e.user_id = :user_id AND e.clock_in >= :since
                ORDER BY e.clock_in DESC LIMIT 20
            """),
            {"user_id": user.id, "since": now - dt.timedelta(days=8)},
        )
        .mappings()
        .all()
    )
    recent = [Entry.model_validate(dict(r)) for r in rows]
    open_entry = next((e for e in recent if e.clock_out is None), None)
    return ClockState(
        open_entry=open_entry,
        planned_shift=None if open_entry else _planned_shift(db, user.id, now),
        recent=recent,
    )


@router.post("/me/time-clock/clock-in", status_code=status.HTTP_201_CREATED)
def clock_in(body: ClockIn, user: UserDep, context: ReadDep) -> Entry:
    db = context.session
    now = dt.datetime.now(dt.UTC)
    time_zone = _time_zone(db)
    _ensure_month_open(db, user.id, {_month_of(now, time_zone)})
    shift = _planned_shift(db, user.id, now)
    location_id = body.location_id or (shift.location_id if shift else None)
    if location_id is None:
        branches = (
            db.execute(
                text("""
                SELECT id FROM app.locations
                WHERE tenant_id = app.current_tenant_id() AND active
                  AND (:scoped = false OR id = ANY(:allowed))
            """),
                {"scoped": context.branches is not None, "allowed": list(context.branches or [])},
            )
            .scalars()
            .all()
        )
        if len(branches) != 1:
            raise HTTPException(status_code=422, detail="location_required")
        location_id = branches[0]
    ensure_branch_allowed(context, location_id)
    try:
        entry_id = db.execute(
            text("""
                INSERT INTO app.time_clock_entries
                    (tenant_id, user_id, location_id, shift_id, clock_in)
                VALUES (app.current_tenant_id(), :user_id, :location_id, :shift_id, :now)
                RETURNING id
            """),
            {
                "user_id": user.id,
                "location_id": location_id,
                "shift_id": shift.id if shift and shift.location_id == location_id else None,
                "now": now,
            },
        ).scalar_one()
    except IntegrityError as error:
        if "time_clock_entries_open" in str(error.orig):
            raise HTTPException(status_code=409, detail="already_clocked_in") from error
        raise HTTPException(status_code=422, detail="invalid_branch") from error
    return _entry(db, entry_id)


@router.post("/me/time-clock/clock-out")
def clock_out(user: UserDep, context: ReadDep) -> Entry:
    db = context.session
    now = dt.datetime.now(dt.UTC)
    row = db.execute(
        text("""
            SELECT id, clock_in FROM app.time_clock_entries
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
              AND clock_out IS NULL
            FOR UPDATE
        """),
        {"user_id": user.id},
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="not_clocked_in")
    # A clock left running overnight is cut at the limit; a manager corrects it afterwards.
    ended = min(now, row.clock_in + MAX_OPEN)
    db.execute(
        text("""
            UPDATE app.time_clock_entries SET clock_out = :ended, updated_at = now() WHERE id = :id
        """),
        {"ended": ended, "id": row.id},
    )
    return _entry(db, row.id)


# -- the manager's month ---------------------------------------------------------------------


def _first_of_month(value: str | None, time_zone: str) -> dt.date:
    if value is None:
        return dt.datetime.now(ZoneInfo(time_zone)).date().replace(day=1)
    try:
        return dt.datetime.strptime(value, "%Y-%m").date()
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid_month") from error


MonthQuery = Annotated[
    str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM, default this month")
]


def _worked(
    session: Session,
    user_id: UUID,
    start: dt.datetime,
    end: dt.datetime,
    time_zone: str,
    rules: ClockRules,
) -> tuple[Breakdown, int]:
    """Hours worked inside [start, end), per day, plus the number of open entries. A running
    entry counts up to now."""
    rows = session.execute(
        text("""
            SELECT clock_in, clock_out FROM app.time_clock_entries
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
              AND app.in_branch(location_id) AND clock_in < :end
              AND coalesce(clock_out, clock_in) >= :start - interval '1 day'
        """),
        {"user_id": user_id, "start": start, "end": end},
    ).all()
    per_day: dict[dt.date, float] = {}
    now = dt.datetime.now(dt.UTC)
    open_count = 0
    for clock_in_, clock_out_ in rows:
        if clock_out_ is None:
            open_count += 1
            clock_out_ = min(now, clock_in_ + MAX_OPEN)
        for day, hours in split_by_day(clock_in_, clock_out_, time_zone).items():
            if start.date() <= day < end.date():
                per_day[day] = per_day.get(day, 0) + hours
    return compute(per_day, rules), open_count


@router.get("/time-clock/month")
def month_overview(context: ApproveDep, month: MonthQuery = None) -> Month:
    """Everyone with shifts or clocked time in the month: planned against worked."""
    db = context.session
    time_zone = _time_zone(db)
    first = _first_of_month(month, time_zone)
    start, end = _month_bounds(first, time_zone)
    rules = _clock_rules(load_rules(db))
    scoped, allowed = context.branches is not None, list(context.branches or [])
    people = db.execute(
        text("""
            WITH wanted AS (
                SELECT user_id FROM app.shifts
                WHERE tenant_id = app.current_tenant_id() AND starts_at >= :start
                  AND starts_at < :end AND app.in_branch(location_id)
                  AND (:scoped = false OR location_id = ANY(:allowed))
                UNION
                SELECT user_id FROM app.time_clock_entries
                WHERE tenant_id = app.current_tenant_id() AND clock_in >= :start
                  AND clock_in < :end AND app.in_branch(location_id)
                  AND (:scoped = false OR location_id = ANY(:allowed))
            )
            SELECT u.id AS user_id, coalesce(u.full_name, u.email) AS user_name,
                   a.approved_at,
                   coalesce((SELECT sum(extract(epoch FROM s.ends_at - s.starts_at)) / 3600
                             FROM app.shifts s
                             WHERE s.tenant_id = app.current_tenant_id() AND s.user_id = u.id
                               AND s.starts_at >= :start AND s.starts_at < :end
                               AND app.in_branch(s.location_id)), 0)::float AS planned_hours,
                   (SELECT count(*) FROM app.shifts s
                    WHERE s.tenant_id = app.current_tenant_id() AND s.user_id = u.id
                      AND s.starts_at >= :start AND s.starts_at < :end AND s.ends_at < now()
                      AND app.in_branch(s.location_id)
                      AND NOT EXISTS (
                          SELECT 1 FROM app.time_clock_entries e
                          WHERE e.tenant_id = s.tenant_id AND e.user_id = s.user_id
                            AND (e.shift_id = s.id
                                 OR (e.clock_in < s.ends_at
                                     AND coalesce(e.clock_out, now()) > s.starts_at)))
                   ) AS missing_shifts,
                   (SELECT count(*) FROM app.time_clock_entries e
                    WHERE e.tenant_id = app.current_tenant_id() AND e.user_id = u.id
                      AND e.clock_in >= :start AND e.clock_in < :end
                      AND e.corrected_by IS NOT NULL) AS corrections
            FROM wanted w
            JOIN app.users u ON u.id = w.user_id
            LEFT JOIN app.time_clock_approvals a
                   ON a.tenant_id = app.current_tenant_id() AND a.user_id = u.id
                  AND a.month = :first
            ORDER BY user_name, u.id
        """),
        {"start": start, "end": end, "first": first, "scoped": scoped, "allowed": allowed},
    ).mappings()
    result = []
    for row in people:
        breakdown, open_count = _worked(db, row["user_id"], start, end, time_zone, rules)
        result.append(
            PersonMonth(
                user_id=row["user_id"],
                user_name=row["user_name"],
                planned_hours=round(row["planned_hours"], 2),
                worked=_hours(breakdown),
                missing_shifts=row["missing_shifts"],
                open_entries=open_count,
                corrections=row["corrections"],
                approved=row["approved_at"] is not None,
                approved_at=row["approved_at"],
            )
        )
    return Month(month=first, people=result)


@router.get("/time-clock/people/{user_id}")
def person_month(user_id: UUID, context: ApproveDep, month: MonthQuery = None) -> PersonDetail:
    """One person's month: totals, hours per day and every entry."""
    _ensure_member_in_reach(context, user_id)
    db = context.session
    time_zone = _time_zone(db)
    first = _first_of_month(month, time_zone)
    start, end = _month_bounds(first, time_zone)
    breakdown, _ = _worked(db, user_id, start, end, time_zone, _clock_rules(load_rules(db)))
    entries = [
        Entry.model_validate(dict(r))
        for r in db.execute(
            text(f"""
                {ENTRY_SELECT}
                WHERE e.user_id = :user_id AND e.clock_in >= :start AND e.clock_in < :end
                  AND app.in_branch(e.location_id)
                ORDER BY e.clock_in
            """),
            {"user_id": user_id, "start": start, "end": end},
        ).mappings()
    ]
    info = (
        db.execute(
            text("""
            SELECT coalesce(u.full_name, u.email) AS user_name,
                   EXISTS (SELECT 1 FROM app.time_clock_approvals a
                           WHERE a.tenant_id = app.current_tenant_id() AND a.user_id = u.id
                             AND a.month = :first) AS approved,
                   coalesce((SELECT sum(extract(epoch FROM s.ends_at - s.starts_at)) / 3600
                             FROM app.shifts s
                             WHERE s.tenant_id = app.current_tenant_id() AND s.user_id = u.id
                               AND s.starts_at >= :start AND s.starts_at < :end
                               AND app.in_branch(s.location_id)), 0)::float AS planned_hours
            FROM app.users u WHERE u.id = :user_id
        """),
            {"user_id": user_id, "first": first, "start": start, "end": end},
        )
        .mappings()
        .one()
    )
    return PersonDetail(
        month=first,
        user_id=user_id,
        user_name=info["user_name"],
        approved=info["approved"],
        planned_hours=round(info["planned_hours"], 2),
        worked=_hours(breakdown),
        days=breakdown.days,
        entries=entries,
    )


@router.post("/time-clock/entries", status_code=status.HTTP_201_CREATED)
def add_entry(body: EntryCreate, context: ApproveDep) -> Entry:
    """A manager records time that was not clocked (forgot to clock in, no phone)."""
    _ensure_member_in_reach(context, body.user_id)
    ensure_branch_allowed(context, body.location_id)
    db = context.session
    time_zone = _time_zone(db)
    _ensure_month_open(
        db,
        body.user_id,
        {_month_of(body.clock_in, time_zone), _month_of(body.clock_out, time_zone)},
    )
    _no_overlap(db, body.user_id, body.clock_in, body.clock_out, None)
    try:
        entry_id = db.execute(
            text("""
                INSERT INTO app.time_clock_entries
                    (tenant_id, user_id, location_id, clock_in, clock_out, source,
                     correction_reason, corrected_by)
                VALUES (app.current_tenant_id(), :user_id, :location_id, :clock_in, :clock_out,
                        'manual', :reason, app.current_user_id())
                RETURNING id
            """),
            body.model_dump(),
        ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=422, detail="invalid_branch") from error
    _audit(
        db,
        "time_clock.add",
        entry_id,
        {
            "user_id": body.user_id,
            "clock_in": body.clock_in,
            "clock_out": body.clock_out,
            "reason": body.reason,
        },
    )
    return _entry(db, entry_id)


def _no_overlap(
    session: Session, user_id: UUID, start: dt.datetime, end: dt.datetime | None, skip: UUID | None
) -> None:
    clash = session.execute(
        text("""
            SELECT 1 FROM app.time_clock_entries
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
              AND (CAST(:skip AS uuid) IS NULL OR id <> :skip)
              AND clock_in < coalesce(CAST(:end AS timestamptz), 'infinity')
              AND coalesce(clock_out, 'infinity') > :start
        """),
        {"user_id": user_id, "start": start, "end": end, "skip": skip},
    ).first()
    if clash is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="entry_overlap")


@router.patch("/time-clock/entries/{entry_id}")
def correct_entry(entry_id: UUID, body: EntryCorrection, context: ApproveDep) -> Entry:
    """Changes the times of an entry (closing a forgotten clock-out is a correction too). The
    reason is kept on the entry and the old and new times go to the audit log."""
    db = context.session
    before = _entry(db, entry_id)
    _ensure_member_in_reach(context, before.user_id)
    time_zone = _time_zone(db)
    clock_in_ = body.clock_in or before.clock_in
    clock_out_ = body.clock_out or before.clock_out
    if clock_out_ is not None and not clock_in_ < clock_out_ <= clock_in_ + MAX_OPEN:
        raise HTTPException(status_code=422, detail="invalid_period")
    months = {_month_of(before.clock_in, time_zone), _month_of(clock_in_, time_zone)}
    _ensure_month_open(db, before.user_id, months)
    _no_overlap(db, before.user_id, clock_in_, clock_out_, entry_id)
    db.execute(
        text("""
            UPDATE app.time_clock_entries
            SET clock_in = :clock_in, clock_out = :clock_out, correction_reason = :reason,
                corrected_by = app.current_user_id(), updated_at = now()
            WHERE id = :id
        """),
        {"id": entry_id, "clock_in": clock_in_, "clock_out": clock_out_, "reason": body.reason},
    )
    _audit(
        db,
        "time_clock.correct",
        entry_id,
        {
            "user_id": before.user_id,
            "from": [before.clock_in, before.clock_out],
            "to": [clock_in_, clock_out_],
            "reason": body.reason,
        },
    )
    return _entry(db, entry_id)


@router.delete("/time-clock/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: UUID, context: ApproveDep, reason: Annotated[str, Query(min_length=1, max_length=200)]
) -> None:
    db = context.session
    before = _entry(db, entry_id)
    _ensure_member_in_reach(context, before.user_id)
    time_zone = _time_zone(db)
    _ensure_month_open(db, before.user_id, {_month_of(before.clock_in, time_zone)})
    db.execute(text("DELETE FROM app.time_clock_entries WHERE id = :id"), {"id": entry_id})
    _audit(
        db,
        "time_clock.delete",
        entry_id,
        {"user_id": before.user_id, "was": [before.clock_in, before.clock_out], "reason": reason},
    )


@router.put("/time-clock/people/{user_id}/approval", status_code=status.HTTP_204_NO_CONTENT)
def approve_month(user_id: UUID, context: ApproveDep, month: MonthQuery = None) -> None:
    """Approves the person's month and locks it. A clock still running blocks it."""
    _ensure_member_in_reach(context, user_id)
    db = context.session
    first = _first_of_month(month, _time_zone(db))
    _, end = _month_bounds(first, _time_zone(db))
    running = db.execute(
        text("""
            SELECT 1 FROM app.time_clock_entries
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
              AND clock_out IS NULL AND clock_in < :end
        """),
        {"user_id": user_id, "end": end},
    ).first()
    if running is not None:
        raise HTTPException(status_code=409, detail="entry_open")
    db.execute(
        text("""
            INSERT INTO app.time_clock_approvals (tenant_id, user_id, month, approved_by)
            VALUES (app.current_tenant_id(), :user_id, :month, app.current_user_id())
            ON CONFLICT DO NOTHING
        """),
        {"user_id": user_id, "month": first},
    )


@router.delete("/time-clock/people/{user_id}/approval", status_code=status.HTTP_204_NO_CONTENT)
def reopen_month(user_id: UUID, context: ApproveDep, month: MonthQuery = None) -> None:
    _ensure_member_in_reach(context, user_id)
    db = context.session
    first = _first_of_month(month, _time_zone(db))
    db.execute(
        text("""
            DELETE FROM app.time_clock_approvals
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id AND month = :month
        """),
        {"user_id": user_id, "month": first},
    )


# -- the overtime rules ----------------------------------------------------------------------


@router.get("/time-clock/rules")
def get_rules(context: ReadDep) -> Rules:
    return load_rules(context.session)


@router.put("/time-clock/rules")
def set_rules(body: Rules, context: SettingsDep) -> Rules:
    context.session.execute(
        text("""
            INSERT INTO app.time_clock_rules
                (tenant_id, work_days_per_week, week_hours, day_hours_5, day_hours_6, tier1_hours,
                 tier1_percent, tier2_percent, rest_day_percent, rest_weekday)
            VALUES (app.current_tenant_id(), :work_days_per_week, :week_hours, :day_hours_5,
                    :day_hours_6, :tier1_hours, :tier1_percent, :tier2_percent,
                    :rest_day_percent, :rest_weekday)
            ON CONFLICT (tenant_id) DO UPDATE SET
                work_days_per_week = excluded.work_days_per_week,
                week_hours = excluded.week_hours, day_hours_5 = excluded.day_hours_5,
                day_hours_6 = excluded.day_hours_6, tier1_hours = excluded.tier1_hours,
                tier1_percent = excluded.tier1_percent, tier2_percent = excluded.tier2_percent,
                rest_day_percent = excluded.rest_day_percent,
                rest_weekday = excluded.rest_weekday, updated_at = now()
        """),
        body.model_dump(),
    )
    return load_rules(context.session)
