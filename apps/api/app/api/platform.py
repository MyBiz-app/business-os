"""Platform console: businesses on the platform and their usage (platform admins only)."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import SessionDep

router = APIRouter(prefix="/platform", tags=["platform"])


def require_platform_admin(session: SessionDep) -> Session:
    if not session.execute(text("SELECT app.is_platform_admin()")).scalar_one():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return session


AdminDep = Annotated[Session, Depends(require_platform_admin)]


class PlatformBusiness(BaseModel):
    id: UUID
    name: str
    vertical: str
    locale: str
    currency: str
    time_zone: str
    created_at: dt.datetime
    members: int
    clients: int
    active_clients: int
    modules: list[str]
    ai_credits_30d: float
    bookings_30d: int
    owner_email: str | None


class UsagePoint(BaseModel):
    day: dt.date
    meter: str
    quantity: float


@router.get("/businesses")
def businesses(db: AdminDep) -> list[PlatformBusiness]:
    rows = db.execute(text("SELECT * FROM app.platform_businesses()")).mappings()
    return [PlatformBusiness.model_validate(dict(row)) for row in rows]


@router.get("/usage")
def usage(
    db: AdminDep,
    tenant_id: Annotated[UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[UsagePoint]:
    """Usage per day and meter, for one business or the whole platform."""
    rows = db.execute(
        text("SELECT * FROM app.platform_usage(:tenant_id, :days)"),
        {"tenant_id": tenant_id, "days": days},
    ).mappings()
    return [UsagePoint.model_validate(dict(row)) for row in rows]


class ContactRequest(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str | None
    business: str | None
    vertical: str | None
    message: str | None
    locale: str
    created_at: dt.datetime


@router.get("/contact-requests")
def contact_requests(db: AdminDep) -> list[ContactRequest]:
    """Businesses that wrote in through the marketing site, newest first."""
    rows = db.execute(text("SELECT * FROM app.platform_contact_requests()")).mappings()
    return [ContactRequest.model_validate(dict(row)) for row in rows]
