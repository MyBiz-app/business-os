"""Shift templates and coverage rules for the shifts board.

A template is a named shift type of one branch, applied with one click when planning. A coverage
rule is the least number of people a branch needs on shift on a weekday between two times; the
coverage report lists the stretches in a date range that fall short. Like shifts, both follow the
current branch (`app.in_branch`)."""

import datetime as dt
from datetime import time, timedelta
from itertools import pairwise
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.availability import Candidate, candidates
from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, require
from app.api.shifts import SHIFT_SELECT, Shift, _branch_visible, _time_zone, drafts_hidden
from app.core.permissions import Permission
from app.schedule.scheduling import local_to_utc

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]

DAY = 1440


class ShiftTemplateFields(BaseModel):
    name: str = Field(min_length=1, max_length=40, description='E.g. "Morning"')
    starts: time
    ends: time = Field(description="Earlier than `starts`: the shift runs past midnight")
    position: str | None = Field(default=None, max_length=60)

    @field_validator("name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("position", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def has_length(self) -> "ShiftTemplateFields":
        if self.starts == self.ends:
            raise ValueError("a shift has a length")
        return self


class ShiftTemplateCreate(ShiftTemplateFields):
    location_id: UUID


class ShiftTemplate(ShiftTemplateCreate):
    id: UUID


TEMPLATE_SELECT = """
    SELECT id, location_id, name, starts, ends, position FROM app.shift_templates
    WHERE app.in_branch(location_id)
"""


@router.get("/shift-templates")
def list_shift_templates(
    context: ReadDep,
    location_id: Annotated[list[UUID] | None, Query(description="Only these branches")] = None,
) -> list[ShiftTemplate]:
    rows = context.session.execute(
        text(
            f"{TEMPLATE_SELECT} AND (CAST(:locations AS uuid[]) IS NULL"
            " OR location_id = ANY(CAST(:locations AS uuid[]))) ORDER BY starts, name"
        ),
        {"locations": [str(i) for i in location_id] if location_id else None},
    ).mappings()
    return [ShiftTemplate.model_validate(dict(row)) for row in rows]


@router.post("/shift-templates", status_code=status.HTTP_201_CREATED)
def create_shift_template(body: ShiftTemplateCreate, context: ManageDep) -> ShiftTemplate:
    if not _branch_visible(context.session, body.location_id):
        raise HTTPException(status_code=422, detail="invalid_reference")
    taken = context.session.execute(
        text(
            "SELECT 1 FROM app.shift_templates WHERE location_id = :l AND lower(name) = lower(:n)"
        ),
        {"l": body.location_id, "n": body.name},
    ).first()
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="template_name_taken")
    row = context.session.execute(
        text("""
            INSERT INTO app.shift_templates (tenant_id, location_id, name, starts, ends, position)
            VALUES (app.current_tenant_id(), :location_id, :name, :starts, :ends, :position)
            RETURNING id, location_id, name, starts, ends, position
        """),
        body.model_dump(),
    ).mappings()
    return ShiftTemplate.model_validate(dict(row.one()))


@router.delete("/shift-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift_template(template_id: UUID, context: ManageDep) -> None:
    deleted = context.session.execute(
        text("DELETE FROM app.shift_templates WHERE id = :id AND app.in_branch(location_id)"),
        {"id": template_id},
    )
    if deleted.rowcount == 0:
        raise not_found()


class CoverageRule(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    starts_minute: int = Field(ge=0, lt=DAY, description="Minutes from midnight")
    ends_minute: int = Field(gt=0, le=DAY, description="Minutes from midnight; 1440 = end of day")
    min_staff: int = Field(ge=1, le=50, description="People needed on shift at the same time")

    @model_validator(mode="after")
    def ordered(self) -> "CoverageRule":
        if self.ends_minute <= self.starts_minute:
            raise ValueError("ends_minute must be after starts_minute")
        return self


class CoverageRules(BaseModel):
    rules: list[CoverageRule] = Field(max_length=100)


def _load_rules(session: Session, location_id: UUID) -> CoverageRules:
    rows = session.execute(
        text("""
            SELECT weekday, starts_minute, ends_minute, min_staff FROM app.coverage_rules
            WHERE location_id = :id ORDER BY weekday, starts_minute, ends_minute
        """),
        {"id": location_id},
    ).mappings()
    return CoverageRules(rules=[CoverageRule.model_validate(dict(r)) for r in rows])


@router.get("/locations/{location_id}/coverage-rules")
def get_coverage_rules(location_id: UUID, context: ReadDep) -> CoverageRules:
    if not _branch_visible(context.session, location_id):
        raise not_found()
    return _load_rules(context.session, location_id)


@router.put("/locations/{location_id}/coverage-rules")
def set_coverage_rules(location_id: UUID, body: CoverageRules, context: ManageDep) -> CoverageRules:
    """Replaces the branch's whole set of rules."""
    if not _branch_visible(context.session, location_id):
        raise not_found()
    context.session.execute(
        text("DELETE FROM app.coverage_rules WHERE location_id = :id"), {"id": location_id}
    )
    if body.rules:
        context.session.execute(
            text("""
                INSERT INTO app.coverage_rules (tenant_id, location_id, weekday, starts_minute,
                                                ends_minute, min_staff)
                VALUES (app.current_tenant_id(), :location, :weekday, :starts_minute,
                        :ends_minute, :min_staff)
            """),
            [{"location": location_id, **r.model_dump()} for r in body.rules],
        )
    return _load_rules(context.session, location_id)


class CoverageGap(BaseModel):
    location_id: UUID
    location_name: str
    day: dt.date
    starts_minute: int
    ends_minute: int
    needed: int
    have: int = Field(description="People on shift through the stretch")
    available: list[Candidate] = Field(
        default_factory=list,
        description="Managers only: people of the branch who said they can work the whole "
        "stretch (`/me/availability`), are not away and have no shift then",
    )


def _gaps(
    rules: list[tuple[int, int, int]], busy: list[tuple[int, int]]
) -> list[tuple[int, int, int, int]]:
    """Stretches of one day where fewer people work than the rules ask. `rules` are
    (start, end, min_staff) of that weekday, `busy` the (start, end) of each shift, all in
    minutes from midnight. Returns (start, end, needed, have), neighbours alike merged."""
    points = sorted({0, DAY, *(p for r in rules for p in r[:2]), *(p for s in busy for p in s)})
    out: list[tuple[int, int, int, int]] = []
    for start, end in pairwise(points):
        needed = max((m for a, b, m in rules if a <= start and end <= b), default=0)
        have = sum(1 for a, b in busy if a <= start and end <= b)
        if have >= needed:
            continue
        if out and out[-1][1] == start and out[-1][2:] == (needed, have):
            out[-1] = (out[-1][0], end, needed, have)
        else:
            out.append((start, end, needed, have))
    return out


@router.get("/shifts/coverage")
def shift_coverage(
    context: ReadDep,
    start: Annotated[dt.date, Query(description="First local date (business time zone)")],
    days: Annotated[int, Query(ge=1, le=42)] = 7,
    location_id: Annotated[list[UUID] | None, Query(description="Only these branches")] = None,
    published_only: Annotated[
        bool, Query(description="Managers: count only the published roster, not drafts")
    ] = False,
) -> list[CoverageGap]:
    """Where a branch has fewer people on shift than its coverage rules ask, day by day. People
    away on time off do not count. Branches without rules are never listed. Managers also get,
    per gap, who said they can work it and is free."""
    session = context.session
    time_zone = _time_zone(session)
    wanted = [str(i) for i in location_id] if location_id else None
    rule_rows = session.execute(
        text("""
            SELECT r.location_id, l.name, r.weekday, r.starts_minute, r.ends_minute, r.min_staff
            FROM app.coverage_rules r JOIN app.locations l ON l.id = r.location_id
            WHERE app.in_branch(r.location_id) AND l.active
              AND (CAST(:locations AS uuid[]) IS NULL
                   OR r.location_id = ANY(CAST(:locations AS uuid[])))
        """),
        {"locations": wanted},
    ).all()
    if not rule_rows:
        return []
    rules: dict[UUID, list[tuple[int, int, int, int]]] = {}
    names: dict[UUID, str] = {}
    for loc, name, weekday, a, b, minimum in rule_rows:
        rules.setdefault(loc, []).append((weekday, a, b, minimum))
        names[loc] = name
    roster = " AND sh.published_at IS NOT NULL" if published_only else drafts_hidden(context)
    rows = session.execute(
        text(
            f"{SHIFT_SELECT} AND sh.starts_at < :to AND sh.ends_at > :from{roster}"
            " AND sh.location_id = ANY(CAST(:locations AS uuid[]))"
        ),
        {
            "from": local_to_utc(start - timedelta(days=1), time.min, time_zone),
            "to": local_to_utc(start + timedelta(days=days), time.min, time_zone),
            "locations": [str(i) for i in rules],
        },
    ).mappings()
    zone = ZoneInfo(time_zone)
    shifts = [Shift.model_validate(dict(r)) for r in rows]
    result: list[CoverageGap] = []
    for loc, loc_rules in rules.items():
        here = [
            (
                s.starts_at.astimezone(zone).replace(tzinfo=None),
                s.ends_at.astimezone(zone).replace(tzinfo=None),
            )
            for s in shifts
            if s.location_id == loc and not s.on_time_off
        ]
        for offset in range(days):
            day = start + timedelta(days=offset)
            midnight = dt.datetime.combine(day, time.min)
            todays = [(a, b, m) for w, a, b, m in loc_rules if w == day.weekday()]
            if not todays:
                continue
            busy = [
                (
                    max(0, int((a - midnight).total_seconds() // 60)),
                    min(DAY, int((b - midnight).total_seconds() // 60)),
                )
                for a, b in here
                if a < midnight + timedelta(days=1) and b > midnight
            ]
            for a, b, needed, have in _gaps(todays, busy):
                result.append(
                    CoverageGap(
                        location_id=loc,
                        location_name=names[loc],
                        day=day,
                        starts_minute=a,
                        ends_minute=b,
                        needed=needed,
                        have=have,
                    )
                )
    result.sort(key=lambda g: (g.day, g.starts_minute, g.location_name))
    if Permission.STAFF_MANAGE in context.permissions:

        def at(day: dt.date, minute: int) -> dt.datetime:
            day, minute = day + timedelta(days=minute // DAY), minute % DAY
            return local_to_utc(day, time(minute // 60, minute % 60), time_zone)

        periods = [
            (g.location_id, at(g.day, g.starts_minute), at(g.day, g.ends_minute)) for g in result
        ]
        for gap, people in zip(result, candidates(session, periods, time_zone), strict=True):
            gap.available = people
    return result
