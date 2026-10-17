"""Closed days and opening the next week to clients."""

import datetime as dt
from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, require
from app.api.schedule import _time_zone
from app.core.permissions import Permission
from app.messaging.notifications import notify_sessions
from app.schedule.release import MAX_AHEAD_DAYS, load_release
from app.schedule.scheduling import local_to_utc

router = APIRouter(tags=["schedule"])

WriteDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_WRITE))]
ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]


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


class PublishedWeek(BaseModel):
    published_until: dt.date = Field(description="Last local date clients can now book")


@router.post("/sessions/publish-week")
def publish_week(context: WriteDep) -> PublishedWeek:
    """Opens the next week for clients ahead of the scheduled release (or the rolling horizon)."""
    db = context.session
    release, time_zone = load_release(db)
    today = datetime.now(ZoneInfo(time_zone)).date()
    until = release.published_until + timedelta(days=7)
    if until > today + timedelta(days=MAX_AHEAD_DAYS):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_published")
    db.execute(
        text("""
            UPDATE app.tenants SET schedule_published_until = :until
            WHERE id = app.current_tenant_id()
        """),
        {"until": until},
    )
    return PublishedWeek(published_until=until)


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
