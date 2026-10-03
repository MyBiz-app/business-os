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
from app.permissions import Permission
from app.scheduling import local_to_utc, weekly_occurrences

router = APIRouter(tags=["schedule"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_WRITE))]

MAX_SERIES_DAYS = 26 * 7  # Series are expanded up front; a background job will extend them.
DEFAULT_SERIES_DAYS = 12 * 7

SessionStatus = Literal["scheduled", "cancelled"]


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
    status: SessionStatus
    notes: str | None


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
           bk.booked, bk.waitlisted,
           sv.id AS service_id, sv.name AS service_name, sv.color AS service_color
    FROM app.sessions s
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.locations l ON l.id = s.location_id
    LEFT JOIN app.rooms r ON r.id = s.room_id
    LEFT JOIN app.users u ON u.id = s.instructor_user_id
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
) -> list[ScheduledSession]:
    time_zone = _time_zone(context.session)
    window_start = local_to_utc(start, time.min, time_zone)
    window_end = local_to_utc(start + timedelta(days=days), time.min, time_zone)
    in_window = "WHERE s.starts_at >= :from AND s.starts_at < :to ORDER BY s.starts_at"
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
        starts = list(
            weekly_occurrences(
                body.date, ends_on, set(body.repeat.weekdays), body.start_time, time_zone
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
                         capacity, weekdays, start_time, duration_minutes, starts_on, ends_on)
                    VALUES
                        (:tenant_id, :service_id, :location_id, :room_id, :instructor_user_id,
                         :capacity, :weekdays, :start_time, :duration, :starts_on, :ends_on)
                    RETURNING id
                """),
                {
                    **placement,
                    "weekdays": body.repeat.weekdays,
                    "start_time": body.start_time,
                    "duration": duration,
                    "starts_on": body.date,
                    "ends_on": ends_on,
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
    return _load(db, session_id)
