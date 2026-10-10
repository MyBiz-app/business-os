"""Employee shifts and branch opening hours (workspace upgrade, phase 1).

Three different times, kept apart on purpose:
- a branch's opening hours (`location_hours`): when the doors are open;
- a member's shifts (`shifts`): when they work, and where;
- a member's availability (`staff_hours`): when clients can book appointments with them.

Shifts follow the current branch like every list (`app.in_branch`), so a member kept to some
branches sees and plans only those. One person never has two overlapping shifts."""

import datetime as dt
from datetime import datetime, time, timedelta
from itertools import pairwise
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, UserDep, require
from app.core.permissions import Permission
from app.schedule.scheduling import local_to_utc

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]
CatalogReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
CatalogWriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]

MAX_SHIFT = timedelta(hours=24)
SHIFT_COLUMNS = ("user_id", "location_id", "starts_at", "ends_at", "position", "note")


class OpeningInterval(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    opens: time
    closes: time

    @model_validator(mode="after")
    def ordered(self) -> "OpeningInterval":
        if self.closes <= self.opens:
            raise ValueError("closes must be after opens")
        return self


class OpeningHours(BaseModel):
    """A branch's week: one or more intervals per open day (a break is the gap between two);
    a day with no interval is closed."""

    intervals: list[OpeningInterval] = Field(max_length=42)

    @model_validator(mode="after")
    def no_overlaps(self) -> "OpeningHours":
        by_day: dict[int, list[OpeningInterval]] = {}
        for interval in self.intervals:
            by_day.setdefault(interval.weekday, []).append(interval)
        for day in by_day.values():
            day.sort(key=lambda i: i.opens)
            for before, after in pairwise(day):
                if after.opens < before.closes:
                    raise ValueError("intervals of a day must not overlap")
        return self


def _branch_visible(session: Session, location_id: UUID) -> bool:
    return session.execute(
        text("SELECT EXISTS (SELECT 1 FROM app.locations WHERE id = :id AND app.in_branch(id))"),
        {"id": location_id},
    ).scalar_one()


def _load_hours(session: Session, location_id: UUID) -> OpeningHours:
    rows = session.execute(
        text("""
            SELECT weekday, opens, closes FROM app.location_hours
            WHERE location_id = :id ORDER BY weekday, opens
        """),
        {"id": location_id},
    ).mappings()
    return OpeningHours(intervals=[OpeningInterval.model_validate(dict(r)) for r in rows])


@router.get("/locations/{location_id}/hours")
def get_opening_hours(location_id: UUID, context: CatalogReadDep) -> OpeningHours:
    if not _branch_visible(context.session, location_id):
        raise not_found()
    return _load_hours(context.session, location_id)


@router.put("/locations/{location_id}/hours")
def set_opening_hours(
    location_id: UUID, body: OpeningHours, context: CatalogWriteDep
) -> OpeningHours:
    """Replaces the branch's whole week."""
    if not _branch_visible(context.session, location_id):
        raise not_found()
    context.session.execute(
        text("DELETE FROM app.location_hours WHERE location_id = :id"), {"id": location_id}
    )
    if body.intervals:
        context.session.execute(
            text("""
                INSERT INTO app.location_hours (tenant_id, location_id, weekday, opens, closes)
                VALUES (app.current_tenant_id(), :location, :weekday, :opens, :closes)
            """),
            [{"location": location_id, **i.model_dump()} for i in body.intervals],
        )
    return _load_hours(context.session, location_id)


class Shift(BaseModel):
    id: UUID
    location_id: UUID
    location_name: str
    user_id: UUID
    user_name: str
    starts_at: datetime
    ends_at: datetime
    position: str | None
    note: str | None
    on_time_off: bool = Field(description="Falls on a day the person is away")
    outside_hours: bool = Field(description="Not within the branch's opening hours (if set)")


class ShiftFields(BaseModel):
    position: str | None = Field(default=None, max_length=60, description="E.g. reception")
    note: str | None = Field(default=None, max_length=200)

    @field_validator("position", "note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class ShiftCreate(ShiftFields):
    user_id: UUID
    location_id: UUID
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_length(self) -> "ShiftCreate":
        if not self.starts_at < self.ends_at <= self.starts_at + MAX_SHIFT:
            raise ValueError("a shift ends after it starts, within 24 hours")
        return self


class ShiftUpdate(ShiftFields):
    user_id: UUID | None = None
    location_id: UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CopyShiftsWeek(BaseModel):
    from_week: dt.date = Field(description="First day of the week to copy (seven days from it)")
    to_week: dt.date = Field(description="First day of the week to fill")


class CopiedShifts(BaseModel):
    created: int
    skipped: int = Field(description="Shifts left out because the person was already working")


SHIFT_SELECT = """
    SELECT sh.id, sh.location_id, l.name AS location_name, sh.user_id,
           coalesce(u.full_name, u.email) AS user_name, sh.starts_at, sh.ends_at,
           sh.position, sh.note,
           EXISTS (
               SELECT 1 FROM app.staff_time_off o
               WHERE o.tenant_id = sh.tenant_id AND o.user_id = sh.user_id
                 AND (sh.starts_at AT TIME ZONE t.time_zone)::date <= o.ends_on
                 AND (sh.ends_at AT TIME ZONE t.time_zone)::date >= o.starts_on
           ) AS on_time_off,
           EXISTS (SELECT 1 FROM app.location_hours h WHERE h.location_id = sh.location_id)
           AND NOT EXISTS (
               SELECT 1 FROM app.location_hours h
               WHERE h.location_id = sh.location_id
                 AND h.weekday = extract(isodow FROM sh.starts_at AT TIME ZONE t.time_zone) - 1
                 AND h.opens <= (sh.starts_at AT TIME ZONE t.time_zone)::time
                 AND h.closes >= (sh.ends_at AT TIME ZONE t.time_zone)::time
                 AND (sh.ends_at AT TIME ZONE t.time_zone)::date
                     = (sh.starts_at AT TIME ZONE t.time_zone)::date
           ) AS outside_hours
    FROM app.shifts sh
    JOIN app.tenants t ON t.id = sh.tenant_id
    JOIN app.locations l ON l.id = sh.location_id
    JOIN app.users u ON u.id = sh.user_id
    WHERE app.in_branch(sh.location_id)
"""


def _time_zone(session: Session) -> str:
    return session.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()


def _load_shift(session: Session, shift_id: UUID) -> Shift:
    row = session.execute(text(f"{SHIFT_SELECT} AND sh.id = :id"), {"id": shift_id}).mappings()
    found = row.first()
    if found is None:
        raise not_found()
    return Shift.model_validate(dict(found))


@router.get("/shifts")
def list_shifts(
    context: ReadDep,
    start: Annotated[dt.date, Query(description="First local date (business time zone)")],
    days: Annotated[int, Query(ge=1, le=42)] = 7,
    location_id: Annotated[
        list[UUID] | None, Query(description="Only these branches (within the person's own)")
    ] = None,
    user_id: Annotated[UUID | None, Query(description="Only this person's shifts")] = None,
) -> list[Shift]:
    time_zone = _time_zone(context.session)
    filters = ""
    params: dict[str, object] = {
        "from": local_to_utc(start, time.min, time_zone),
        "to": local_to_utc(start + timedelta(days=days), time.min, time_zone),
    }
    if location_id:
        filters += " AND sh.location_id = ANY(CAST(:locations AS uuid[]))"
        params["locations"] = [str(i) for i in location_id]
    if user_id:
        filters += " AND sh.user_id = :user_id"
        params["user_id"] = user_id
    rows = context.session.execute(
        text(
            f"{SHIFT_SELECT} AND sh.starts_at < :to AND sh.ends_at > :from {filters}"
            " ORDER BY sh.starts_at, user_name"
        ),
        params,
    ).mappings()
    return [Shift.model_validate(dict(row)) for row in rows]


def _check_and_lock(
    session: Session,
    user_id: UUID,
    location_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    ignore: UUID | None = None,
) -> None:
    """The person works here and is free then; holds a lock on them until the commit."""
    member = session.execute(
        text("""
            SELECT 1 FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = :id
        """),
        {"id": user_id},
    ).first()
    if member is None or not _branch_visible(session, location_id):
        raise HTTPException(status_code=422, detail="invalid_reference")
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('shift:' || :id, 0))"),
        {"id": str(user_id)},
    )
    clash = session.execute(
        text("""
            SELECT 1 FROM app.shifts
            WHERE user_id = :user AND starts_at < :ends AND ends_at > :starts
              AND (CAST(:ignore AS uuid) IS NULL OR id <> CAST(:ignore AS uuid))
        """),
        {"user": user_id, "starts": starts_at, "ends": ends_at, "ignore": ignore},
    ).first()
    if clash is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="shift_overlap")


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(body: ShiftCreate, user: UserDep, context: ManageDep) -> Shift:
    _check_and_lock(context.session, body.user_id, body.location_id, body.starts_at, body.ends_at)
    shift_id = context.session.execute(
        text("""
            INSERT INTO app.shifts (tenant_id, location_id, user_id, starts_at, ends_at,
                                    position, note, created_by)
            VALUES (app.current_tenant_id(), :location_id, :user_id, :starts_at, :ends_at,
                    :position, :note, :created_by)
            RETURNING id
        """),
        {**body.model_dump(), "created_by": user.id},
    ).scalar_one()
    return _load_shift(context.session, shift_id)


@router.patch("/shifts/{shift_id}")
def update_shift(shift_id: UUID, body: ShiftUpdate, context: ManageDep) -> Shift:
    current = _load_shift(context.session, shift_id)
    changes = body.model_dump(exclude_unset=True)
    merged = {**current.model_dump(), **{k: v for k, v in changes.items() if v is not None}}
    for key in ("position", "note"):
        if key in changes:
            merged[key] = changes[key]
    if not merged["starts_at"] < merged["ends_at"] <= merged["starts_at"] + MAX_SHIFT:
        raise HTTPException(status_code=422, detail="invalid_period")
    _check_and_lock(
        context.session,
        merged["user_id"],
        merged["location_id"],
        merged["starts_at"],
        merged["ends_at"],
        ignore=shift_id,
    )
    context.session.execute(
        text("""
            UPDATE app.shifts
            SET user_id = :user_id, location_id = :location_id, starts_at = :starts_at,
                ends_at = :ends_at, position = :position, note = :note
            WHERE id = :id
        """),
        {key: merged[key] for key in SHIFT_COLUMNS} | {"id": shift_id},
    )
    return _load_shift(context.session, shift_id)


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(shift_id: UUID, context: ManageDep) -> None:
    _load_shift(context.session, shift_id)  # 404 outside the person's branches
    context.session.execute(text("DELETE FROM app.shifts WHERE id = :id"), {"id": shift_id})


@router.post("/shifts/copy-week")
def copy_shifts_week(body: CopyShiftsWeek, user: UserDep, context: ManageDep) -> CopiedShifts:
    """Repeats a week's shifts (in the visible branches) in another week, at the same local
    times; a shift that would clash with one already there is skipped."""
    source, target = body.from_week, body.to_week
    if abs((target - source).days) < 7:
        raise HTTPException(status_code=422, detail="weeks_overlap")
    time_zone = _time_zone(context.session)
    rows = context.session.execute(
        text(f"""
            {SHIFT_SELECT} AND sh.starts_at >= :from AND sh.starts_at < :to
            ORDER BY sh.starts_at
        """),
        {
            "from": local_to_utc(source, time.min, time_zone),
            "to": local_to_utc(source + timedelta(days=7), time.min, time_zone),
        },
    ).mappings()
    shifts = [Shift.model_validate(dict(row)) for row in rows]
    created = skipped = 0
    offset = target - source
    for shift in shifts:
        # Same local wall-clock time (daylight saving can move the UTC instant).
        local_start = shift.starts_at.astimezone(ZoneInfo(time_zone))
        starts = local_to_utc(local_start.date() + offset, local_start.time(), time_zone)
        ends = starts + (shift.ends_at - shift.starts_at)
        try:
            with context.session.begin_nested():
                _check_and_lock(context.session, shift.user_id, shift.location_id, starts, ends)
                context.session.execute(
                    text("""
                        INSERT INTO app.shifts (tenant_id, location_id, user_id, starts_at,
                                                ends_at, position, note, created_by)
                        VALUES (app.current_tenant_id(), :location, :user, :starts, :ends,
                                :position, :note, :created_by)
                    """),
                    {
                        "location": shift.location_id,
                        "user": shift.user_id,
                        "starts": starts,
                        "ends": ends,
                        "position": shift.position,
                        "note": shift.note,
                        "created_by": user.id,
                    },
                )
            created += 1
        except HTTPException:
            skipped += 1
    return CopiedShifts(created=created, skipped=skipped)
