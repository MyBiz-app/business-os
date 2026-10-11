"""Time-off requests: staff ask for days off, a manager approves or declines.

Approving adds the same `staff_time_off` row a manager would add by hand, so the shift board,
the free-time search and the coverage rules need no special case. Staff see only their own
requests; people who manage staff see everyone's."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, UserDep, require
from app.core.permissions import Permission

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]

RequestStatus = Literal["pending", "approved", "declined", "cancelled"]


class TimeOffRequestCreate(BaseModel):
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("reason", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def ordered(self) -> "TimeOffRequestCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must not be before starts_on")
        if (self.ends_on - self.starts_on).days > 366:
            raise ValueError("at most a year at a time")
        return self


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=200, description="Shown to the requester")

    @field_validator("note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class TimeOffRequest(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    starts_on: dt.date
    ends_on: dt.date
    reason: str | None
    status: RequestStatus
    decided_by_name: str | None
    decided_at: dt.datetime | None
    decision_note: str | None
    created_at: dt.datetime
    shift_count: int = Field(description="Shifts the person already has on those days")


SELECT = """
    SELECT r.id, r.user_id, coalesce(u.full_name, u.email) AS user_name, r.starts_on, r.ends_on,
           r.reason, r.status, coalesce(d.full_name, d.email) AS decided_by_name, r.decided_at,
           r.decision_note, r.created_at,
           (SELECT count(*) FROM app.shifts sh
            WHERE sh.tenant_id = r.tenant_id AND sh.user_id = r.user_id
              AND app.in_branch(sh.location_id)
              AND (sh.starts_at AT TIME ZONE t.time_zone)::date <= r.ends_on
              AND (sh.ends_at AT TIME ZONE t.time_zone)::date >= r.starts_on) AS shift_count
    FROM app.time_off_requests r
    JOIN app.tenants t ON t.id = r.tenant_id
    JOIN app.users u ON u.id = r.user_id
    LEFT JOIN app.users d ON d.id = r.decided_by
"""


def _load(session: Session, request_id: UUID) -> TimeOffRequest:
    row = session.execute(text(f"{SELECT} WHERE r.id = :id"), {"id": request_id}).mappings().first()
    if row is None:
        raise not_found()
    return TimeOffRequest.model_validate(dict(row))


def _today(session: Session) -> dt.date:
    return session.execute(
        text(
            "SELECT (now() AT TIME ZONE time_zone)::date FROM app.tenants"
            " WHERE id = app.current_tenant_id()"
        )
    ).scalar_one()


@router.post("/time-off-requests", status_code=status.HTTP_201_CREATED)
def request_time_off(body: TimeOffRequestCreate, user: UserDep, context: ReadDep) -> TimeOffRequest:
    """The signed-in person asks for days off, to be decided by a manager."""
    db = context.session
    if body.ends_on < _today(db):
        raise HTTPException(status_code=422, detail="invalid_period")
    overlap = db.execute(
        text("""
            SELECT 1 FROM app.time_off_requests
            WHERE user_id = :u AND status IN ('pending', 'approved')
              AND starts_on <= :ends AND ends_on >= :starts
        """),
        {"u": user.id, "starts": body.starts_on, "ends": body.ends_on},
    ).first()
    if overlap is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request_overlap")
    request_id = db.execute(
        text("""
            INSERT INTO app.time_off_requests (tenant_id, user_id, starts_on, ends_on, reason)
            VALUES (app.current_tenant_id(), :u, :starts_on, :ends_on, :reason)
            RETURNING id
        """),
        {"u": user.id, **body.model_dump()},
    ).scalar_one()
    return _load(db, request_id)


@router.get("/time-off-requests")
def list_time_off_requests(
    user: UserDep,
    context: ReadDep,
    mine: Annotated[bool, Query(description="Only the signed-in person's own")] = False,
    request_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
) -> list[TimeOffRequest]:
    """Pending requests first, then the latest decided ones. Without the staff-management
    permission the list is always the person's own."""
    only_mine = mine or Permission.STAFF_MANAGE not in context.permissions
    filters = ""
    params: dict[str, object] = {"u": user.id, "status": request_status}
    if only_mine:
        filters += " AND r.user_id = :u"
    if request_status is not None:
        filters += " AND r.status = :status"
    rows = context.session.execute(
        text(
            f"{SELECT} WHERE r.ends_on >= (now() AT TIME ZONE t.time_zone)::date - 30 {filters}"
            " ORDER BY (r.status = 'pending') DESC, r.starts_on, r.created_at LIMIT 200"
        ),
        params,
    ).mappings()
    return [TimeOffRequest.model_validate(dict(r)) for r in rows]


@router.delete("/time-off-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_time_off_request(request_id: UUID, user: UserDep, context: ReadDep) -> None:
    """The requester withdraws a request that is still waiting."""
    cancelled = context.session.execute(
        text("""
            UPDATE app.time_off_requests SET status = 'cancelled'
            WHERE id = :id AND user_id = :u AND status = 'pending' RETURNING id
        """),
        {"id": request_id, "u": user.id},
    ).scalar()
    if cancelled is None:
        raise not_found()


def _decide(
    request_id: UUID, new_status: str, note: str | None, user: UserDep, context: TenantContext
) -> TimeOffRequest:
    db = context.session
    current = (
        db.execute(
            text("""
            SELECT user_id, starts_on, ends_on, reason, status FROM app.time_off_requests
            WHERE id = :id FOR UPDATE
        """),
            {"id": request_id},
        )
        .mappings()
        .first()
    )
    if current is None:
        raise not_found()
    if current["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request_not_pending")
    time_off_id = None
    if new_status == "approved":
        time_off_id = db.execute(
            text("""
                INSERT INTO app.staff_time_off (tenant_id, user_id, starts_on, ends_on, reason)
                VALUES (app.current_tenant_id(), :u, :starts_on, :ends_on, :reason)
                RETURNING id
            """),
            {
                "u": current["user_id"],
                "starts_on": current["starts_on"],
                "ends_on": current["ends_on"],
                "reason": current["reason"],
            },
        ).scalar_one()
    db.execute(
        text("""
            UPDATE app.time_off_requests
            SET status = :status, decided_by = :by, decided_at = now(), decision_note = :note,
                time_off_id = :time_off_id
            WHERE id = :id
        """),
        {
            "status": new_status,
            "by": user.id,
            "note": note,
            "time_off_id": time_off_id,
            "id": request_id,
        },
    )
    return _load(db, request_id)


@router.post("/time-off-requests/{request_id}/approve")
def approve_time_off_request(
    request_id: UUID, body: Decision, user: UserDep, context: ManageDep
) -> TimeOffRequest:
    return _decide(request_id, "approved", body.note, user, context)


@router.post("/time-off-requests/{request_id}/decline")
def decline_time_off_request(
    request_id: UUID, body: Decision, user: UserDep, context: ManageDep
) -> TimeOffRequest:
    return _decide(request_id, "declined", body.note, user, context)
