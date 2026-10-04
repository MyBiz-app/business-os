"""The owner's side of audited support access: let platform support in for a limited time,
end it early, and see what support looked at (see migration 0023)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import TenantContext, get_tenant_context

router = APIRouter(prefix="/support-access", tags=["settings"])


def require_owner(context: Annotated[TenantContext, Depends(get_tenant_context)]) -> TenantContext:
    if context.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_only")
    return context


OwnerDep = Annotated[TenantContext, Depends(require_owner)]


class Grant(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime


class SupportVisit(BaseModel):
    occurred_at: datetime
    actor_email: str | None
    path: str | None


class SupportStatus(BaseModel):
    active: Grant | None
    visits: list[SupportVisit] = Field(description="The latest 50 support requests")


class GrantCreate(BaseModel):
    hours: int = Field(ge=1, le=72, description="How long support may look in")


def _status(context: TenantContext) -> SupportStatus:
    db = context.session
    active = (
        db.execute(
            text("""
                SELECT id, created_at, expires_at FROM app.support_grants
                WHERE revoked_at IS NULL AND expires_at > now()
                ORDER BY expires_at DESC LIMIT 1
            """)
        )
        .mappings()
        .first()
    )
    visits = db.execute(
        text("""
            SELECT a.occurred_at, a.details->>'email' AS actor_email, a.details->>'path' AS path
            FROM app.audit_log a
            WHERE a.action = 'support.view'
            ORDER BY a.occurred_at DESC LIMIT 50
        """)
    ).mappings()
    return SupportStatus(
        active=Grant.model_validate(dict(active)) if active else None,
        visits=[SupportVisit.model_validate(dict(v)) for v in visits],
    )


@router.get("")
def support_status(context: OwnerDep) -> SupportStatus:
    return _status(context)


@router.post("", status_code=status.HTTP_201_CREATED)
def grant_support(body: GrantCreate, context: OwnerDep) -> SupportStatus:
    """Lets platform support see the business (read-only) for the given hours."""
    db = context.session
    db.execute(
        text("""
            UPDATE app.support_grants SET revoked_at = now(), revoked_by = app.current_user_id()
            WHERE revoked_at IS NULL AND expires_at > now()
        """)
    )
    db.execute(
        text("""
            INSERT INTO app.support_grants (tenant_id, granted_by, expires_at)
            VALUES (:tenant_id, app.current_user_id(), now() + make_interval(hours => :hours))
        """),
        {"tenant_id": context.tenant_id, "hours": body.hours},
    )
    return _status(context)


@router.delete("")
def revoke_support(context: OwnerDep) -> SupportStatus:
    context.session.execute(
        text("""
            UPDATE app.support_grants SET revoked_at = now(), revoked_by = app.current_user_id()
            WHERE revoked_at IS NULL AND expires_at > now()
        """)
    )
    return _status(context)
