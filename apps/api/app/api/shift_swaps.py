"""Shift swaps: a person offers one of their shifts to a named colleague; the colleague
accepts; a manager approves; then the shift changes hands.

The hand-over is the normal change of the shift's person, so the board, the clash checks and
the roster-change emails need no special case. Staff see swaps they are part of; people who
manage staff see all of them."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, UserDep, require
from app.api.shifts import _check_and_lock
from app.core.permissions import Permission

router = APIRouter(tags=["shifts"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]

SwapStatus = Literal[
    "pending_colleague", "pending_manager", "approved", "declined", "refused", "cancelled"
]


class SwapCreate(BaseModel):
    shift_id: UUID
    to_user_id: UUID
    note: str | None = Field(default=None, max_length=200)

    @field_validator("note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class SwapDecision(BaseModel):
    note: str | None = Field(default=None, max_length=200, description="Shown to both people")

    @field_validator("note", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class ShiftSwap(BaseModel):
    id: UUID
    shift_id: UUID
    location_name: str
    starts_at: str
    ends_at: str
    from_user_id: UUID
    from_user_name: str
    to_user_id: UUID
    to_user_name: str
    note: str | None
    status: SwapStatus
    decided_by_name: str | None
    decision_note: str | None
    created_at: str


SELECT = """
    SELECT s.id, s.shift_id, l.name AS location_name, sh.starts_at::text AS starts_at,
           sh.ends_at::text AS ends_at, s.from_user_id,
           coalesce(f.full_name, f.email) AS from_user_name, s.to_user_id,
           coalesce(t.full_name, t.email) AS to_user_name, s.note, s.status,
           coalesce(d.full_name, d.email) AS decided_by_name, s.decision_note,
           s.created_at::text AS created_at
    FROM app.shift_swaps s
    JOIN app.shifts sh ON sh.id = s.shift_id
    JOIN app.locations l ON l.id = sh.location_id
    JOIN app.users f ON f.id = s.from_user_id
    JOIN app.users t ON t.id = s.to_user_id
    LEFT JOIN app.users d ON d.id = s.decided_by
    WHERE app.in_branch(sh.location_id)
"""


def _load(session: Session, swap_id: UUID) -> ShiftSwap:
    row = session.execute(text(f"{SELECT} AND s.id = :id"), {"id": swap_id}).mappings().first()
    if row is None:
        raise not_found()
    return ShiftSwap.model_validate(dict(row))


@router.post("/shift-swaps", status_code=status.HTTP_201_CREATED)
def offer_swap(body: SwapCreate, user: UserDep, context: ReadDep) -> ShiftSwap:
    """The signed-in person offers one of their own upcoming, published shifts to a colleague."""
    db = context.session
    if body.to_user_id == user.id:
        raise HTTPException(status_code=422, detail="invalid_reference")
    shift = db.execute(
        text("""
            SELECT id FROM app.shifts
            WHERE id = :id AND user_id = :u AND app.in_branch(location_id)
              AND published_at IS NOT NULL AND starts_at > now()
        """),
        {"id": body.shift_id, "u": user.id},
    ).first()
    colleague = db.execute(
        text(
            "SELECT 1 FROM app.tenant_members WHERE tenant_id = app.current_tenant_id()"
            " AND user_id = :u"
        ),
        {"u": body.to_user_id},
    ).first()
    if shift is None or colleague is None:
        raise not_found()
    try:
        with db.begin_nested():
            swap_id = db.execute(
                text("""
                    INSERT INTO app.shift_swaps
                        (tenant_id, shift_id, from_user_id, to_user_id, note)
                    VALUES (app.current_tenant_id(), :shift_id, :u, :to_user_id, :note)
                    RETURNING id
                """),
                {"u": user.id, **body.model_dump()},
            ).scalar_one()
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="swap_open") from error
    return _load(db, swap_id)


@router.get("/shift-swaps")
def list_swaps(
    user: UserDep,
    context: ReadDep,
    swap_status: Annotated[SwapStatus | None, Query(alias="status")] = None,
) -> list[ShiftSwap]:
    """Open swaps first, then the latest closed ones; the shift must not be over a month ago."""
    filters = ""
    params: dict[str, object] = {"u": user.id, "status": swap_status}
    if Permission.STAFF_MANAGE not in context.permissions:
        filters += " AND (s.from_user_id = :u OR s.to_user_id = :u)"
    if swap_status is not None:
        filters += " AND s.status = :status"
    rows = context.session.execute(
        text(
            f"{SELECT} AND sh.ends_at > now() - interval '30 days' {filters}"
            " ORDER BY (s.status IN ('pending_colleague', 'pending_manager')) DESC,"
            " sh.starts_at LIMIT 200"
        ),
        params,
    ).mappings()
    return [ShiftSwap.model_validate(dict(r)) for r in rows]


def _row(session: Session, swap_id: UUID, lock: bool = True):
    row = (
        session.execute(
            text(
                "SELECT s.shift_id, s.from_user_id, s.to_user_id, s.status FROM app.shift_swaps s"
                " JOIN app.shifts sh ON sh.id = s.shift_id"
                " WHERE s.id = :id AND app.in_branch(sh.location_id)"
                + (" FOR UPDATE OF s" if lock else "")
            ),
            {"id": swap_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return row


@router.post("/shift-swaps/{swap_id}/accept")
def accept_swap(swap_id: UUID, user: UserDep, context: ReadDep) -> ShiftSwap:
    """The colleague agrees to take the shift; it then waits for a manager."""
    return _colleague_answer(swap_id, "pending_manager", user, context)


@router.post("/shift-swaps/{swap_id}/refuse")
def refuse_swap(swap_id: UUID, user: UserDep, context: ReadDep) -> ShiftSwap:
    """The colleague turns the offer down."""
    return _colleague_answer(swap_id, "refused", user, context)


def _colleague_answer(
    swap_id: UUID, new_status: str, user: UserDep, context: TenantContext
) -> ShiftSwap:
    db = context.session
    row = _row(db, swap_id)
    if row["to_user_id"] != user.id:
        raise not_found()
    if row["status"] != "pending_colleague":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="swap_not_pending")
    db.execute(
        text("UPDATE app.shift_swaps SET status = :s, colleague_at = now() WHERE id = :id"),
        {"s": new_status, "id": swap_id},
    )
    return _load(db, swap_id)


@router.delete("/shift-swaps/{swap_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_swap(swap_id: UUID, user: UserDep, context: ReadDep) -> None:
    """The person who offered the shift withdraws an open swap."""
    row = _row(context.session, swap_id)
    if row["from_user_id"] != user.id:
        raise not_found()
    if row["status"] not in ("pending_colleague", "pending_manager"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="swap_not_pending")
    context.session.execute(
        text("UPDATE app.shift_swaps SET status = 'cancelled' WHERE id = :id"), {"id": swap_id}
    )


def _manager_decision(
    swap_id: UUID, new_status: str, note: str | None, user: UserDep, context: TenantContext
) -> ShiftSwap:
    db = context.session
    row = _row(db, swap_id)
    if row["status"] != "pending_manager":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="swap_not_pending")
    if new_status == "approved":
        shift = (
            db.execute(
                text("""
                SELECT user_id, location_id, station_id, starts_at, ends_at FROM app.shifts
                WHERE id = :id FOR UPDATE
            """),
                {"id": row["shift_id"]},
            )
            .mappings()
            .first()
        )
        # The shift must still be the offerer's and not started; the colleague must be free.
        if shift is None or shift["user_id"] != row["from_user_id"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="shift_changed")
        _check_and_lock(
            db,
            row["to_user_id"],
            shift["location_id"],
            shift["starts_at"],
            shift["ends_at"],
            ignore=row["shift_id"],
            station_id=shift["station_id"],
        )
        db.execute(
            text("UPDATE app.shifts SET user_id = :u WHERE id = :id"),
            {"u": row["to_user_id"], "id": row["shift_id"]},
        )
    db.execute(
        text("""
            UPDATE app.shift_swaps
            SET status = :s, decided_by = :by, decided_at = now(), decision_note = :note
            WHERE id = :id
        """),
        {"s": new_status, "by": user.id, "note": note, "id": swap_id},
    )
    return _load(db, swap_id)


@router.post("/shift-swaps/{swap_id}/approve")
def approve_swap(swap_id: UUID, body: SwapDecision, user: UserDep, context: ManageDep) -> ShiftSwap:
    return _manager_decision(swap_id, "approved", body.note, user, context)


@router.post("/shift-swaps/{swap_id}/decline")
def decline_swap(swap_id: UUID, body: SwapDecision, user: UserDep, context: ManageDep) -> ShiftSwap:
    return _manager_decision(swap_id, "declined", body.note, user, context)
