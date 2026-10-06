import datetime as dt
from datetime import datetime, time, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.bookings import lock_session, promote_waitlist
from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, require
from app.notifications import live_clients, notify, notify_sessions, session_snapshot
from app.permissions import Permission
from app.scheduling import local_to_utc, weekly_occurrences

router = APIRouter(tags=["schedule"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_WRITE))]

MAX_SERIES_DAYS = 26 * 7  # Series are expanded up front; a background job will extend them.
DEFAULT_SERIES_DAYS = 12 * 7

SessionStatus = Literal["scheduled", "cancelled"]
JobStatus = Literal["scheduled", "on_the_way", "in_progress", "done"]


class Placement(BaseModel):
    location_id: UUID | None = None
    room_id: UUID | None = None
    instructor_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def blank_notes(cls, value: object) -> object:
        return blank_to_none(value)


class Repeat(BaseModel):
    weekdays: list[int] = Field(min_length=1, description="0 = Monday … 6 = Sunday")
    ends_on: dt.date | None = None

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("weekdays are 0 (Monday) to 6 (Sunday)")
        return sorted(set(value))


class SessionCreate(Placement):
    service_id: UUID
    date: dt.date = Field(description="Local date in the business's time zone")
    start_time: time = Field(description="Local wall-clock time")
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    repeat: Repeat | None = None

    @model_validator(mode="after")
    def bounded_series(self) -> "SessionCreate":
        if self.repeat and self.repeat.ends_on:
            if self.repeat.ends_on < self.date:
                raise ValueError("repeat.ends_on is before date")
            if (self.repeat.ends_on - self.date).days > MAX_SERIES_DAYS:
                raise ValueError(f"a series can span at most {MAX_SERIES_DAYS} days")
        return self


class SessionUpdate(Placement):
    date: dt.date | None = None
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    status: SessionStatus | None = None


class ServiceSummary(BaseModel):
    id: UUID
    name: str
    color: str | None


class ScheduledSession(BaseModel):
    id: UUID
    series_id: UUID | None
    service: ServiceSummary
    location_id: UUID | None
    location_name: str | None
    room_id: UUID | None
    room_name: str | None
    instructor_user_id: UUID | None
    instructor_email: str | None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked: int
    waitlisted: int
    series_open_ended: bool | None = Field(
        description="For a session in a weekly series: whether the series keeps going"
    )
    status: SessionStatus
    notes: str | None
    booking_mode: Literal["class", "appointment", "resource"] = Field(
        description="appointment: a one-to-one booking with the instructor;"
        " resource: a room or court reserved by the hour"
    )
    appointment_client: str | None = Field(
        description="For an appointment or a reservation: who it is with"
    )
    price_amount: int | None = Field(
        default=None, description="For a reservation: its price, fixed when it was made"
    )
    price_currency: str | None = None
    paid: bool | None = Field(default=None, description="For a reservation: whether it is paid")
    address: str | None = Field(default=None, description="An on-site job: where (#42)")
    address_notes: str | None = Field(
        default=None, description="An on-site job: how to get in (gate code, floor)"
    )
    job_status: JobStatus | None = Field(default=None, description="An on-site job's progress")
    travel_minutes: int = Field(default=0, description="Time to get there, before the job")


class OptionItem(BaseModel):
    id: UUID
    name: str


class ServiceOption(OptionItem):
    duration_minutes: int
    capacity: int


class RoomOption(OptionItem):
    location_id: UUID


class InstructorOption(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None


class ScheduleOptions(BaseModel):
    services: list[ServiceOption]
    locations: list[OptionItem]
    rooms: list[RoomOption]
    instructors: list[InstructorOption]


class CreatedSessions(BaseModel):
    series_id: UUID | None
    session_ids: list[UUID]


SESSION_SELECT = """
    SELECT s.id, s.series_id, s.location_id, l.name AS location_name, s.room_id,
           r.name AS room_name, s.instructor_user_id, u.email AS instructor_email,
           s.starts_at, s.ends_at, s.capacity, s.status, s.notes,
           bk.booked, bk.waitlisted, ss.open_ended AS series_open_ended,
           sv.id AS service_id, sv.name AS service_name, sv.color AS service_color,
           sv.booking_mode, s.price_amount, s.price_currency,
           CASE WHEN s.reserved THEN EXISTS (
               SELECT 1 FROM app.payments p JOIN app.bookings b ON b.id = p.booking_id
               WHERE b.session_id = s.id AND p.status = 'succeeded'
           ) END AS paid,
           CASE WHEN sv.booking_mode <> 'class' THEN (
               SELECT trim(c.first_name || ' ' || coalesce(c.last_name, ''))
               FROM app.bookings b JOIN app.clients c ON c.id = b.client_id
               WHERE b.session_id = s.id AND b.status <> 'cancelled'
               ORDER BY b.created_at LIMIT 1
           ) END AS appointment_client,
           s.address, a.notes AS address_notes, s.job_status, s.travel_minutes
    FROM app.sessions s
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.locations l ON l.id = s.location_id
    LEFT JOIN app.rooms r ON r.id = s.room_id
    LEFT JOIN app.users u ON u.id = s.instructor_user_id
    LEFT JOIN app.session_series ss ON ss.id = s.series_id
    LEFT JOIN app.client_addresses a ON a.id = s.address_id
    CROSS JOIN LATERAL app.session_counts(s.id) bk
"""


def _to_model(row: Any) -> ScheduledSession:
    data = dict(row)
    data["service"] = {
        "id": data.pop("service_id"),
        "name": data.pop("service_name"),
        "color": data.pop("service_color"),
    }
    return ScheduledSession.model_validate(data)


def _time_zone(session: Session) -> str:
    return session.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()


def _invalid_reference() -> HTTPException:
    """A referenced service, location, room or instructor is not part of this business."""
    return HTTPException(status_code=422, detail="invalid_reference")


def _load(session: Session, session_id: UUID) -> ScheduledSession:
    row = (
        session.execute(text(f"{SESSION_SELECT} WHERE s.id = :id"), {"id": session_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return _to_model(row)


@router.get("/sessions/options")
def schedule_options(context: WriteDep) -> ScheduleOptions:
    """Everything the "new session" form can pick from (active items only)."""
    db = context.session
    services = db.execute(
        text("""
            SELECT id, name, duration_minutes, capacity FROM app.services
            WHERE active ORDER BY name
        """)
    ).mappings()
    locations = db.execute(
        text("SELECT id, name FROM app.locations WHERE active ORDER BY name")
    ).mappings()
    rooms = db.execute(
        text("""
            SELECT r.id, r.name, r.location_id FROM app.rooms r
            JOIN app.locations l ON l.id = r.location_id
            WHERE r.active AND l.active ORDER BY r.name
        """)
    ).mappings()
    instructors = db.execute(
        text("""
            SELECT m.user_id, u.email, u.full_name
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = app.current_tenant_id()
            ORDER BY coalesce(u.full_name, u.email)
        """)
    ).mappings()
    return ScheduleOptions(
        services=[ServiceOption.model_validate(dict(r)) for r in services],
        locations=[OptionItem.model_validate(dict(r)) for r in locations],
        rooms=[RoomOption.model_validate(dict(r)) for r in rooms],
        instructors=[InstructorOption.model_validate(dict(r)) for r in instructors],
    )


@router.get("/sessions")
def list_sessions(
    context: ReadDep,
    start: Annotated[dt.date, Query(description="First local date (business time zone)")],
    days: Annotated[int, Query(ge=1, le=42)] = 7,
    mine: Annotated[bool, Query(description="Only sessions the user teaches")] = False,
) -> list[ScheduledSession]:
    time_zone = _time_zone(context.session)
    window_start = local_to_utc(start, time.min, time_zone)
    window_end = local_to_utc(start + timedelta(days=days), time.min, time_zone)
    teaching = "AND s.instructor_user_id = app.current_user_id()" if mine else ""
    # An appointment whose booking was cancelled frees the time; it is not shown.
    in_window = (
        f"WHERE s.starts_at >= :from AND s.starts_at < :to {teaching}"
        # sessions without a branch show in every branch
        " AND (s.location_id IS NULL OR app.in_branch(s.location_id))"
        " AND (sv.booking_mode = 'class' OR bk.booked + bk.waitlisted > 0)"
        " ORDER BY s.starts_at"
    )
    rows = context.session.execute(
        text(f"{SESSION_SELECT} {in_window}"),
        {"from": window_start, "to": window_end},
    ).mappings()
    return [_to_model(row) for row in rows]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_sessions(body: SessionCreate, context: WriteDep) -> CreatedSessions:
    db = context.session
    service = (
        db.execute(
            text("SELECT duration_minutes, capacity FROM app.services WHERE id = :id"),
            {"id": body.service_id},
        )
        .mappings()
        .first()
    )
    if service is None:
        raise _invalid_reference()

    time_zone = _time_zone(db)
    duration = body.duration_minutes or service["duration_minutes"]
    capacity = body.capacity or service["capacity"]
    placement = {
        "tenant_id": context.tenant_id,
        "service_id": body.service_id,
        "location_id": body.location_id,
        "room_id": body.room_id,
        "instructor_user_id": body.instructor_user_id,
        "capacity": capacity,
    }

    series_id: UUID | None = None
    if body.repeat:
        ends_on = body.repeat.ends_on or body.date + timedelta(days=DEFAULT_SERIES_DAYS)
        closed = set(
            db.execute(
                text("SELECT day FROM app.closed_days WHERE day BETWEEN :from AND :to"),
                {"from": body.date, "to": ends_on},
            ).scalars()
        )
        starts = list(
            weekly_occurrences(
                body.date,
                ends_on,
                set(body.repeat.weekdays),
                body.start_time,
                time_zone,
                skip=closed,
            )
        )
    else:
        ends_on = body.date
        starts = [local_to_utc(body.date, body.start_time, time_zone)]
    if not starts:
        raise HTTPException(status_code=422, detail="no_occurrences")

    try:
        if body.repeat:
            series_id = db.execute(
                text("""
                    INSERT INTO app.session_series
                        (tenant_id, service_id, location_id, room_id, instructor_user_id,
                         capacity, weekdays, start_time, duration_minutes, starts_on, ends_on,
                         open_ended)
                    VALUES
                        (:tenant_id, :service_id, :location_id, :room_id, :instructor_user_id,
                         :capacity, :weekdays, :start_time, :duration, :starts_on, :ends_on,
                         :open_ended)
                    RETURNING id
                """),
                {
                    **placement,
                    "weekdays": body.repeat.weekdays,
                    "start_time": body.start_time,
                    "duration": duration,
                    "starts_on": body.date,
                    "ends_on": ends_on,
                    # Without an end date the series keeps going (app.jobs extends it).
                    "open_ended": body.repeat.ends_on is None,
                },
            ).scalar_one()
        ids = (
            db.execute(
                text("""
                INSERT INTO app.sessions
                    (tenant_id, series_id, service_id, location_id, room_id, instructor_user_id,
                     capacity, notes, starts_at, ends_at)
                SELECT :tenant_id, :series_id, :service_id, :location_id, :room_id,
                       :instructor_user_id, :capacity, :notes, start_at,
                       start_at + make_interval(mins => :duration)
                FROM unnest(CAST(:starts AS timestamptz[])) AS start_at
                RETURNING id
            """),
                {
                    **placement,
                    "series_id": series_id,
                    "notes": body.notes,
                    "starts": starts,
                    "duration": duration,
                },
            )
            .scalars()
            .all()
        )
    except IntegrityError as error:
        raise _invalid_reference() from error
    return CreatedSessions(series_id=series_id, session_ids=list(ids))


@router.get("/sessions/{session_id}")
def get_session(session_id: UUID, context: ReadDep) -> ScheduledSession:
    return _load(context.session, session_id)


@router.patch("/sessions/{session_id}")
def update_session(session_id: UUID, body: SessionUpdate, context: WriteDep) -> ScheduledSession:
    """Changes one occurrence; the rest of its series is not affected."""
    db = context.session
    lock_session(db, session_id)
    current = _load(db, session_id)
    changes = body.model_dump(exclude_unset=True)

    assignments: dict[str, Any] = {
        key: changes[key]
        for key in ("location_id", "room_id", "instructor_user_id", "notes")
        if key in changes
    }
    for key in ("capacity", "status"):
        if changes.get(key) is not None:
            assignments[key] = changes[key]

    if any(changes.get(key) is not None for key in ("date", "start_time", "duration_minutes")):
        time_zone = _time_zone(db)
        local_start = current.starts_at.astimezone(ZoneInfo(time_zone))
        new_start = local_to_utc(
            changes.get("date") or local_start.date(),
            changes.get("start_time") or local_start.time(),
            time_zone,
        )
        duration = changes.get("duration_minutes") or int(
            (current.ends_at - current.starts_at).total_seconds() // 60
        )
        assignments["starts_at"] = new_start
        assignments["ends_at"] = new_start + timedelta(minutes=duration)

    set_sql = ", ".join([*(f"{key} = :{key}" for key in assignments), "updated_at = now()"])
    try:
        db.execute(
            text(f"UPDATE app.sessions SET {set_sql} WHERE id = :id"),
            {**assignments, "id": session_id},
        )
    except IntegrityError as error:
        raise _invalid_reference() from error
    promote_waitlist(db, session_id)  # more capacity (or a restored session) frees spots
    updated = _load(db, session_id)
    if updated.starts_at > datetime.now(dt.UTC):
        if current.status == "scheduled" and updated.status == "cancelled":
            notify(
                db,
                context.tenant_id,
                live_clients(db, session_id),
                "session_cancelled",
                session_snapshot(db, session_id),
            )
        elif updated.status == "scheduled" and updated.starts_at != current.starts_at:
            notify(
                db,
                context.tenant_id,
                live_clients(db, session_id),
                "session_moved",
                {**session_snapshot(db, session_id), "previous_starts_at": current.starts_at},
            )
    return updated


class SeriesEnd(BaseModel):
    last_date: dt.date = Field(description="Last local date with sessions; later ones end")


class SeriesEnded(BaseModel):
    cancelled: int = Field(description="Later sessions cancelled (they had no bookings)")
    kept: int = Field(description="Later sessions kept because clients are booked")


@router.post("/series/{series_id}/end")
def end_series(series_id: UUID, body: SeriesEnd, context: WriteDep) -> SeriesEnded:
    """Stops a weekly series after a date: no more occurrences are generated, and later
    sessions without bookings are cancelled. Sessions with bookings stay, to be handled
    one by one (the business must tell those clients)."""
    db = context.session
    series = db.execute(
        text("SELECT starts_on FROM app.session_series WHERE id = :id FOR UPDATE"),
        {"id": series_id},
    ).first()
    if series is None:
        raise not_found()
    if body.last_date < series.starts_on:
        raise HTTPException(status_code=422, detail="before_series_start")
    time_zone = _time_zone(db)
    after = local_to_utc(body.last_date + timedelta(days=1), time.min, time_zone)
    db.execute(
        text("""
            UPDATE app.session_series SET open_ended = false, ends_on = :last_date
            WHERE id = :id
        """),
        {"id": series_id, "last_date": body.last_date},
    )
    counts = db.execute(
        text("""
            WITH later AS (
                SELECT s.id, EXISTS (
                    SELECT 1 FROM app.bookings b
                    WHERE b.session_id = s.id AND b.status <> 'cancelled'
                ) AS booked
                FROM app.sessions s
                WHERE s.series_id = :id AND s.starts_at >= :after AND s.status = 'scheduled'
            ),
            cancelled AS (
                UPDATE app.sessions SET status = 'cancelled', updated_at = now()
                WHERE id IN (SELECT id FROM later WHERE NOT booked)
                RETURNING id
            )
            SELECT (SELECT count(*) FROM cancelled) AS cancelled,
                   (SELECT count(*) FROM later WHERE booked) AS kept
        """),
        {"id": series_id, "after": after},
    ).one()
    return SeriesEnded(cancelled=counts.cancelled, kept=counts.kept)


class SeriesUpdate(Placement):
    from_date: dt.date = Field(description="Local date of the first session to change")
    start_time: time
    duration_minutes: int = Field(ge=5, le=1440)
    capacity: int = Field(ge=1, le=1000)


class SeriesUpdated(BaseModel):
    updated: int = Field(description="Sessions changed (scheduled, on or after from_date)")


@router.patch("/series/{series_id}")
def update_series(series_id: UUID, body: SeriesUpdate, context: WriteDep) -> SeriesUpdated:
    """Changes time, length, capacity, place, instructor and notes of this and all later
    sessions of a series; new occurrences the daily job adds follow the new settings.
    Bookings stay; booked clients are told when the time changes."""
    db = context.session
    exists = db.execute(
        text("SELECT 1 FROM app.session_series WHERE id = :id FOR UPDATE"), {"id": series_id}
    ).scalar()
    if exists is None:
        raise not_found()
    time_zone = _time_zone(db)
    params = {
        "id": series_id,
        "after": local_to_utc(body.from_date, time.min, time_zone),
        "start_time": body.start_time,
        "duration": body.duration_minutes,
        "capacity": body.capacity,
        "location_id": body.location_id,
        "room_id": body.room_id,
        "instructor_user_id": body.instructor_user_id,
        "notes": body.notes,
        "time_zone": time_zone,
    }
    try:
        db.execute(
            text("""
                UPDATE app.session_series
                SET start_time = :start_time, duration_minutes = :duration,
                    capacity = :capacity, location_id = :location_id, room_id = :room_id,
                    instructor_user_id = :instructor_user_id
                WHERE id = :id
            """),
            params,
        )
        changed = (
            db.execute(
                text("""
                    WITH targets AS (
                        SELECT s.id, s.starts_at AS previous_starts_at,
                               (((s.starts_at AT TIME ZONE :time_zone)::date + :start_time)
                                AT TIME ZONE :time_zone) AS new_start
                        FROM app.sessions s
                        WHERE s.series_id = :id AND s.status = 'scheduled'
                          AND s.starts_at >= :after
                        FOR UPDATE
                    )
                    UPDATE app.sessions s
                    SET starts_at = t.new_start,
                        ends_at = t.new_start + make_interval(mins => :duration),
                        capacity = :capacity, location_id = :location_id, room_id = :room_id,
                        instructor_user_id = :instructor_user_id, notes = :notes,
                        updated_at = now()
                    FROM targets t
                    WHERE s.id = t.id
                    RETURNING s.id, t.previous_starts_at, s.starts_at
                """),
                params,
            )
            .mappings()
            .all()
        )
    except IntegrityError as error:
        raise _invalid_reference() from error

    now = datetime.now(dt.UTC)
    for row in changed:
        promote_waitlist(db, row["id"])  # capacity may have grown
    moved = [
        r for r in changed if r["starts_at"] != r["previous_starts_at"] and r["starts_at"] > now
    ]
    notify_sessions(
        db,
        context.tenant_id,
        "session_moved",
        [r["id"] for r in moved],
        [r["previous_starts_at"] for r in moved],
    )
    return SeriesUpdated(updated=len(changed))


class WeekCopy(BaseModel):
    from_date: dt.date = Field(description="First local date of the week to copy")
    to_date: dt.date = Field(description="First local date of the target week")


class WeekCopied(BaseModel):
    created: int
    skipped: int = Field(description="Already in the target week (same class and time)")


@router.post("/sessions/copy-week")
def copy_week(body: WeekCopy, context: WriteDep) -> WeekCopied:
    """Copies the one-off sessions of a week (7 days from from_date) to another week, at the
    same local weekday and time. Weekly series are left out: they repeat on their own."""
    shift = (body.to_date - body.from_date).days
    if shift == 0 or shift % 7 != 0:
        raise HTTPException(status_code=422, detail="not_a_week_apart")
    db = context.session
    time_zone = _time_zone(db)
    result = (
        db.execute(
            text("""
                WITH source AS (
                    SELECT s.*,
                           ((s.starts_at AT TIME ZONE :tz) + make_interval(days => :shift))
                               AT TIME ZONE :tz AS new_start
                    FROM app.sessions s
                    WHERE s.series_id IS NULL AND s.status = 'scheduled'
                      AND s.starts_at >= :from_at AND s.starts_at < :to_at
                ),
                fresh AS (
                    SELECT src.* FROM source src
                    WHERE NOT EXISTS (
                        SELECT 1 FROM app.sessions s
                        WHERE s.service_id = src.service_id AND s.starts_at = src.new_start
                          AND s.status = 'scheduled'
                          AND s.room_id IS NOT DISTINCT FROM src.room_id
                    )
                ),
                created AS (
                    INSERT INTO app.sessions
                        (tenant_id, service_id, location_id, room_id, instructor_user_id,
                         capacity, notes, starts_at, ends_at)
                    SELECT tenant_id, service_id, location_id, room_id, instructor_user_id,
                           capacity, notes, new_start, new_start + (ends_at - starts_at)
                    FROM fresh
                    RETURNING 1
                )
                SELECT (SELECT count(*) FROM created) AS created,
                       (SELECT count(*) FROM source) - (SELECT count(*) FROM created)
                           AS skipped
            """),
            {
                "tz": time_zone,
                "shift": shift,
                "from_at": local_to_utc(body.from_date, time.min, time_zone),
                "to_at": local_to_utc(body.from_date + timedelta(days=7), time.min, time_zone),
            },
        )
        .mappings()
        .one()
    )
    return WeekCopied(created=result["created"], skipped=result["skipped"])


class ClosedDay(BaseModel):
    id: UUID
    day: dt.date
    reason: str | None


class ClosedDayCreate(BaseModel):
    day: dt.date
    reason: str | None = Field(default=None, max_length=120)

    @field_validator("reason", mode="before")
    @classmethod
    def blank_reason(cls, value: object) -> object:
        return blank_to_none(value)


class ClosedDayCreated(BaseModel):
    closed_day: ClosedDay
    cancelled_sessions: int


@router.get("/closed-days")
def list_closed_days(
    context: ReadDep, start: Annotated[dt.date | None, Query()] = None
) -> list[ClosedDay]:
    """Closed days from `start` (default: today, local) on."""
    db = context.session
    rows = db.execute(
        text("""
            SELECT id, day, reason FROM app.closed_days
            WHERE day >= coalesce(CAST(:start AS date),
                                  (SELECT (now() AT TIME ZONE time_zone)::date
                                   FROM app.tenants WHERE id = app.current_tenant_id()))
            ORDER BY day LIMIT 200
        """),
        {"start": start},
    ).mappings()
    return [ClosedDay.model_validate(dict(row)) for row in rows]


@router.post("/closed-days", status_code=status.HTTP_201_CREATED)
def close_day(body: ClosedDayCreate, context: WriteDep) -> ClosedDayCreated:
    """Marks a day closed and cancels its scheduled sessions; booked clients are told."""
    db = context.session
    try:
        row = (
            db.execute(
                text("""
                    INSERT INTO app.closed_days (tenant_id, day, reason, created_by)
                    VALUES (:tenant_id, :day, :reason, app.current_user_id())
                    RETURNING id, day, reason
                """),
                {"tenant_id": context.tenant_id, "day": body.day, "reason": body.reason},
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_closed"
        ) from error
    time_zone = _time_zone(db)
    sessions = db.execute(
        text("""
            UPDATE app.sessions SET status = 'cancelled', updated_at = now()
            WHERE status = 'scheduled' AND starts_at >= :from AND starts_at < :to
            RETURNING id, starts_at
        """),
        {
            "from": local_to_utc(body.day, time.min, time_zone),
            "to": local_to_utc(body.day + timedelta(days=1), time.min, time_zone),
        },
    ).all()
    now = datetime.now(dt.UTC)
    upcoming = [session_id for session_id, starts_at in sessions if starts_at > now]
    notify_sessions(db, context.tenant_id, "session_cancelled", upcoming)
    return ClosedDayCreated(
        closed_day=ClosedDay.model_validate(dict(row)), cancelled_sessions=len(sessions)
    )


@router.delete("/closed-days/{closed_day_id}", status_code=status.HTTP_204_NO_CONTENT)
def reopen_day(closed_day_id: UUID, context: WriteDep) -> None:
    """Opens the day again for new sessions; sessions cancelled when it closed stay cancelled."""
    deleted = context.session.execute(
        text("DELETE FROM app.closed_days WHERE id = :id"), {"id": closed_day_id}
    ).rowcount
    if not deleted:
        raise not_found()
