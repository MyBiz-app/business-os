"""Shift availability: the hours of the week a person says they can work shifts.

A person sets their own week (`/me/availability`), or a manager sets it for them. Saying nothing
means no limit: their shifts are never flagged. A shift outside the week is flagged on the shift
itself (`outside_availability` in `app.api.shifts`), so the board warns while a manager assigns
it, and the coverage report (`app.api.shift_planning`) suggests who can fill a gap."""

from datetime import datetime, time
from itertools import pairwise
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, require
from app.core.permissions import Permission

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]


class WeeklyWindow(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    starts: time
    ends: time

    @model_validator(mode="after")
    def ordered(self) -> "WeeklyWindow":
        if self.ends <= self.starts:
            raise ValueError("ends must be after starts")
        return self


class Availability(BaseModel):
    """The hours of the week a person can work; an empty week means they have not said."""

    windows: list[WeeklyWindow] = Field(max_length=42)

    @model_validator(mode="after")
    def no_overlaps(self) -> "Availability":
        ordered = sorted(self.windows, key=lambda w: (w.weekday, w.starts))
        for before, after in pairwise(ordered):
            if before.weekday == after.weekday and after.starts < before.ends:
                raise ValueError("windows of a day must not overlap")
        return self


class MemberAvailability(Availability):
    user_id: UUID
    user_name: str


def _member(session: Session, user_id: UUID) -> bool:
    return (
        session.execute(
            text("""
                SELECT 1 FROM app.tenant_members
                WHERE tenant_id = app.current_tenant_id() AND user_id = :id
            """),
            {"id": user_id},
        ).first()
        is not None
    )


def _load_availability(session: Session, user_id: UUID) -> Availability:
    rows = session.execute(
        text("""
            SELECT weekday, starts, ends FROM app.staff_availability
            WHERE tenant_id = app.current_tenant_id() AND user_id = :id
            ORDER BY weekday, starts
        """),
        {"id": user_id},
    ).mappings()
    return Availability(windows=[WeeklyWindow.model_validate(dict(r)) for r in rows])


def _save_availability(session: Session, user_id: UUID, body: Availability) -> Availability:
    session.execute(
        text("""
            DELETE FROM app.staff_availability
            WHERE tenant_id = app.current_tenant_id() AND user_id = :id
        """),
        {"id": user_id},
    )
    if body.windows:
        session.execute(
            text("""
                INSERT INTO app.staff_availability (tenant_id, user_id, weekday, starts, ends)
                VALUES (app.current_tenant_id(), :user_id, :weekday, :starts, :ends)
            """),
            [{"user_id": user_id, **w.model_dump()} for w in body.windows],
        )
    return _load_availability(session, user_id)


@router.get("/me/availability")
def get_my_availability(user: UserDep, context: ReadDep) -> Availability:
    return _load_availability(context.session, user.id)


@router.put("/me/availability")
def set_my_availability(body: Availability, user: UserDep, context: ReadDep) -> Availability:
    """Replaces the person's own week."""
    return _save_availability(context.session, user.id, body)


@router.get("/staff/{user_id}/availability")
def get_availability(user_id: UUID, context: ManageDep) -> Availability:
    if not _member(context.session, user_id):
        raise not_found()
    return _load_availability(context.session, user_id)


@router.put("/staff/{user_id}/availability")
def set_availability(user_id: UUID, body: Availability, context: ManageDep) -> Availability:
    """A manager records the week for someone (e.g. who told them in person)."""
    if not _member(context.session, user_id):
        raise not_found()
    return _save_availability(context.session, user_id, body)


@router.get("/shifts/availability")
def list_availability(context: ManageDep) -> list[MemberAvailability]:
    """Everyone's stated week, for the board; people who have not said are left out."""
    rows = context.session.execute(
        text("""
            SELECT a.user_id, coalesce(u.full_name, u.email) AS user_name,
                   a.weekday, a.starts, a.ends
            FROM app.staff_availability a
            JOIN app.users u ON u.id = a.user_id
            WHERE a.tenant_id = app.current_tenant_id()
            ORDER BY user_name, a.user_id, a.weekday, a.starts
        """)
    ).mappings()
    people: dict[UUID, MemberAvailability] = {}
    for row in rows:
        person = people.setdefault(
            row["user_id"],
            MemberAvailability(user_id=row["user_id"], user_name=row["user_name"], windows=[]),
        )
        person.windows.append(WeeklyWindow(**{k: row[k] for k in ("weekday", "starts", "ends")}))
    return list(people.values())


class Candidate(BaseModel):
    user_id: UUID
    user_name: str


def candidates(
    session: Session, periods: list[tuple[UUID, datetime, datetime]], time_zone: str
) -> list[list[Candidate]]:
    """For each (branch, starts, ends), in one query: members of the branch who said they can
    work the whole period, are not away that day and have no shift then."""
    found: list[list[Candidate]] = [[] for _ in periods]
    if not periods:
        return found
    rows = session.execute(
        text("""
            SELECT g.idx, m.user_id, coalesce(u.full_name, u.email) AS user_name
            FROM unnest(CAST(:idx AS int[]), CAST(:locations AS uuid[]),
                        CAST(:starts AS timestamptz[]), CAST(:ends AS timestamptz[]))
                 AS g(idx, location_id, starts_at, ends_at)
            JOIN app.tenant_members m
              ON m.tenant_id = app.current_tenant_id()
             AND (cardinality(m.location_ids) = 0 OR g.location_id = ANY(m.location_ids))
            JOIN app.users u ON u.id = m.user_id
            WHERE EXISTS (
                      SELECT 1 FROM app.staff_availability a
                      WHERE a.tenant_id = m.tenant_id AND a.user_id = m.user_id
                  )
              AND NOT app.outside_availability(m.tenant_id, m.user_id, g.starts_at,
                                               g.ends_at, :zone)
              AND NOT EXISTS (
                  SELECT 1 FROM app.staff_time_off o
                  WHERE o.tenant_id = m.tenant_id AND o.user_id = m.user_id
                    AND (g.starts_at AT TIME ZONE :zone)::date <= o.ends_on
                    AND (g.ends_at AT TIME ZONE :zone)::date >= o.starts_on
              )
              AND NOT EXISTS (
                  SELECT 1 FROM app.shifts s
                  WHERE s.tenant_id = m.tenant_id AND s.user_id = m.user_id
                    AND s.starts_at < g.ends_at AND s.ends_at > g.starts_at
              )
            ORDER BY g.idx, user_name
        """),
        {
            "idx": list(range(len(periods))),
            "locations": [str(p[0]) for p in periods],
            "starts": [p[1] for p in periods],
            "ends": [p[2] for p in periods],
            "zone": time_zone,
        },
    ).mappings()
    for row in rows:
        found[row["idx"]].append(Candidate(user_id=row["user_id"], user_name=row["user_name"]))
    return found
