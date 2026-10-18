"""The smart waitlist (round 7, R30; migration 0132).

The database decides who is waiting for a spot that opens (`app.waitlist_on_freed`) and
cleans up when it is taken (`app.waitlist_on_booked`): they are SECURITY DEFINER functions
because the client who cancels cannot read other clients' requests. This module is the thin
Python side: the working modes, the hooks the booking code calls, and when a request expires."""

from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schedule.scheduling import local_to_utc

WaitlistMode = Literal["off", "auto", "first_come", "manual"]
RequestKind = Literal["slot", "range", "day"]

MAX_ACTIVE_REQUESTS = 5  # per client and business, so nobody signs up for the whole schedule


def mode_for(db: Session, service_id: UUID) -> str:
    """What happens when a spot of this service opens: the service's own setting, else the
    business's setting for its kind (class, appointment or resource); `off` when the waitlist
    is switched off."""
    return (
        db.execute(
            text("SELECT app.waitlist_mode_for(:id)"), {"id": service_id}
        ).scalar_one_or_none()
        or "off"
    )


def spot_opened(db: Session, session_id: UUID) -> int:
    """A spot of the session may have opened: tells the waiting clients (who is told depends on
    the mode). The caller holds the session lock. Returns how many clients were told."""
    return db.execute(text("SELECT app.waitlist_on_freed(:id)"), {"id": session_id}).scalar_one()


def spot_taken(db: Session, session_id: UUID, client_id: UUID) -> None:
    """The client now holds a spot in the session: their matching requests are done, and the
    others who were told about that spot are told it is gone."""
    db.execute(
        text("SELECT app.waitlist_on_booked(:session, :client)"),
        {"session": session_id, "client": client_id},
    )


def request_expiry(
    kind: RequestKind, day: date, to_time: time | None, starts_at: datetime | None, zone: str
) -> datetime:
    """When a request stops mattering: the slot starts, the range ends, or the day ends."""
    if kind == "slot" and starts_at is not None:
        return starts_at
    if kind == "range" and to_time is not None:
        return local_to_utc(day, to_time, zone)
    return local_to_utc(day + timedelta(days=1), time.min, zone)
