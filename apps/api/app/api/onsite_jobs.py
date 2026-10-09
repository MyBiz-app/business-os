"""On-site jobs (#42, decision X11): clients' addresses, a technician's jobs of the day and
their status.

A job is an appointment of an on-site service: it happens at an address of the client and
takes the technician from its travel time before it (see migration 0047). Staff manage every
client's addresses; clients manage their own in the app. A job's status moves forward
(scheduled → on the way → in progress → done) by its technician or anyone who manages
bookings; "done" checks the client in."""

import datetime as dt
from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, ensure_not_erased, not_found, set_clause
from app.api.deps import ClientDep, TenantContext, require
from app.api.schedule import JobStatus
from app.core.permissions import Permission
from app.schedule.scheduling import local_to_utc

router = APIRouter(tags=["jobs"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]
ScheduleDep = Annotated[TenantContext, Depends(require(Permission.SCHEDULE_READ))]

# The order a job moves through; it can go back one step if pressed by mistake.
ORDER: tuple[JobStatus, ...] = ("scheduled", "on_the_way", "in_progress", "done")


class Address(BaseModel):
    id: UUID
    client_id: UUID
    label: str | None = Field(description="Home, office…")
    street: str
    city: str
    details: str | None = Field(description="Floor, apartment")
    notes: str | None = Field(description="How to get in: gate code, parking")
    active: bool
    created_at: datetime


class AddressCreate(BaseModel):
    label: str | None = Field(default=None, max_length=40)
    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=80)
    details: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("label", "street", "city", "details", "notes", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return blank_to_none(value)


class AddressUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=40)
    street: str | None = Field(default=None, min_length=1, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    details: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    active: bool | None = None

    @field_validator("label", "street", "city", "details", "notes", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return blank_to_none(value)


class JobStatusUpdate(BaseModel):
    status: JobStatus


class Job(BaseModel):
    """One on-site job in a technician's day."""

    session_id: UUID
    booking_id: UUID | None
    service_name: str
    starts_at: datetime
    ends_at: datetime
    travel_minutes: int
    address: str | None
    address_notes: str | None
    job_status: JobStatus
    technician_user_id: UUID | None
    technician_name: str | None
    client_id: UUID | None
    client_name: str | None
    client_phone: str | None


COLUMNS = "id, client_id, label, street, city, details, notes, active, created_at"


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _list(db: Session, client_id: UUID) -> list[Address]:
    rows = db.execute(
        text(f"""
            SELECT {COLUMNS} FROM app.client_addresses WHERE client_id = :client_id
            ORDER BY NOT active, created_at
        """),
        {"client_id": client_id},
    ).mappings()
    return [Address.model_validate(dict(row)) for row in rows]


def _create(db: Session, tenant_id: UUID, client_id: UUID, body: AddressCreate) -> Address:
    ensure_not_erased(db, client_id)
    if body.street is None or body.city is None:
        raise _unprocessable("street and city are required")
    try:
        row = (
            db.execute(
                text(f"""
                    INSERT INTO app.client_addresses
                        (tenant_id, client_id, label, street, city, details, notes)
                    VALUES (:tenant_id, :client_id, :label, :street, :city, :details, :notes)
                    RETURNING {COLUMNS}
                """),
                {**body.model_dump(), "tenant_id": tenant_id, "client_id": client_id},
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:  # no such client in this business
        raise not_found() from error
    return Address.model_validate(dict(row))


def _update(db: Session, address_id: UUID, body: AddressUpdate) -> Address:
    changes = body.model_dump(exclude_unset=True)
    for required in ("street", "city", "active"):
        if required in changes and changes[required] is None:
            del changes[required]
    if changes:
        row = db.execute(
            text(
                f"UPDATE app.client_addresses SET {set_clause(changes)}"
                f" WHERE id = :id RETURNING {COLUMNS}"
            ),
            {**changes, "id": address_id},
        )
    else:
        row = db.execute(
            text(f"SELECT {COLUMNS} FROM app.client_addresses WHERE id = :id"),
            {"id": address_id},
        )
    found = row.mappings().first()
    if found is None:
        raise not_found()
    return Address.model_validate(dict(found))


JOB_SELECT = """
    SELECT s.id AS session_id, b.id AS booking_id, sv.name AS service_name,
           s.starts_at, s.ends_at, s.travel_minutes, s.address, a.notes AS address_notes,
           s.job_status, s.instructor_user_id AS technician_user_id,
           coalesce(nullif(u.full_name, ''), u.email) AS technician_name,
           c.id AS client_id,
           trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
           c.phone AS client_phone
    FROM app.sessions s
    JOIN app.services sv ON sv.id = s.service_id
    LEFT JOIN app.client_addresses a ON a.id = s.address_id
    LEFT JOIN app.users u ON u.id = s.instructor_user_id
    LEFT JOIN LATERAL (
        SELECT b.id, b.client_id FROM app.bookings b
        WHERE b.session_id = s.id AND b.status <> 'cancelled'
        ORDER BY b.created_at LIMIT 1
    ) b ON true
    LEFT JOIN app.clients c ON c.id = b.client_id
"""


# --- Staff: addresses -------------------------------------------------------------------------


@router.get("/clients/{client_id}/addresses")
def client_addresses(client_id: UUID, context: ReadDep) -> list[Address]:
    return _list(context.session, client_id)


@router.post("/clients/{client_id}/addresses", status_code=status.HTTP_201_CREATED)
def add_address(client_id: UUID, body: AddressCreate, context: WriteDep) -> Address:
    return _create(context.session, context.tenant_id, client_id, body)


@router.patch("/addresses/{address_id}")
def update_address(address_id: UUID, body: AddressUpdate, context: WriteDep) -> Address:
    return _update(context.session, address_id, body)


# --- Staff: jobs ------------------------------------------------------------------------------


@router.get("/jobs")
def jobs_of_day(
    context: ScheduleDep,
    day: Annotated[dt.date, Query(alias="date", description="Local date")],
    staff_user_id: Annotated[
        UUID | None, Query(description="One technician; default: the signed-in user")
    ] = None,
    everyone: Annotated[bool, Query(description="All technicians (managers)")] = False,
) -> list[Job]:
    """A day's on-site jobs in order: the signed-in technician's by default."""
    db = context.session
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    start = local_to_utc(day, time.min, time_zone)
    me = db.execute(text("SELECT app.current_user_id()")).scalar_one()
    if (everyone or (staff_user_id and staff_user_id != me)) and (
        Permission.BOOKINGS_MANAGE not in context.permissions
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    rows = db.execute(
        text(f"""
            {JOB_SELECT}
            WHERE s.job_status IS NOT NULL AND s.status = 'scheduled'
              AND s.starts_at >= :from AND s.starts_at < :to
              AND (:everyone OR s.instructor_user_id = :staff)
            ORDER BY s.starts_at
        """),
        {
            "from": start,
            "to": start + timedelta(days=1),
            "everyone": everyone,
            "staff": staff_user_id or me,
        },
    ).mappings()
    return [Job.model_validate(dict(row)) for row in rows]


@router.post("/jobs/{session_id}/status")
def set_job_status(session_id: UUID, body: JobStatusUpdate, context: ScheduleDep) -> Job:
    """Moves a job one step forward (or back one step): its technician, or anyone who manages
    bookings. Done checks the client in."""
    db = context.session
    row = (
        db.execute(
            text("""
                SELECT s.job_status, s.instructor_user_id = app.current_user_id() AS mine
                FROM app.sessions s
                WHERE s.id = :id AND s.job_status IS NOT NULL AND s.status = 'scheduled'
                FOR UPDATE
            """),
            {"id": session_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    if not row["mine"] and Permission.BOOKINGS_MANAGE not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    current, wanted = ORDER.index(row["job_status"]), ORDER.index(body.status)
    if abs(wanted - current) > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid_transition")
    db.execute(
        text("UPDATE app.sessions SET job_status = :status, updated_at = now() WHERE id = :id"),
        {"status": body.status, "id": session_id},
    )
    # Done is the visit: the client is checked in (and back to booked if undone).
    db.execute(
        text("""
            UPDATE app.bookings
            SET status = CASE WHEN :done THEN 'checked_in' ELSE 'booked' END,
                checked_in_at = CASE WHEN :done THEN now() END, updated_at = now()
            WHERE session_id = :id AND status IN ('booked', 'checked_in')
        """),
        {"done": body.status == "done", "id": session_id},
    )
    job = db.execute(text(f"{JOB_SELECT} WHERE s.id = :id"), {"id": session_id}).mappings().one()
    return Job.model_validate(dict(job))


# --- Client app -------------------------------------------------------------------------------


@client_router.get("/addresses")
def my_addresses(context: ClientDep) -> list[Address]:
    return _list(context.session, context.client_id)


@client_router.post("/addresses", status_code=status.HTTP_201_CREATED)
def add_my_address(body: AddressCreate, context: ClientDep) -> Address:
    return _create(context.session, context.tenant_id, context.client_id, body)


@client_router.patch("/addresses/{address_id}")
def update_my_address(address_id: UUID, body: AddressUpdate, context: ClientDep) -> Address:
    # The client policy only lets a client see (and so change) their own addresses.
    return _update(context.session, address_id, body)
