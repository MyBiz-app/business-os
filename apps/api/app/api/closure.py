"""Closing a business account (decision X20): the owner closes it, the data stays for 90 days
(the owner can reopen), then the delete-closed-businesses job removes it for good.
While closed the business is locked for staff and clients (see `get_tenant_context`)."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import TenantContext, get_tenant_context
from app.core import events
from app.core.mfa import check_sensitive_action
from app.core.retention import CLOSED_BUSINESS_GRACE_DAYS

router = APIRouter(prefix="/tenants/current/closure", tags=["settings"])

# The only paths that still work in a closed business (the owner must be able to reopen it).
CLOSURE_PATH = "/tenants/current/closure"


def require_owner(context: Annotated[TenantContext, Depends(get_tenant_context)]) -> TenantContext:
    if context.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_only")
    check_sensitive_action(context.session, context.aal)
    return context


OwnerDep = Annotated[TenantContext, Depends(require_owner)]


class Closure(BaseModel):
    closed_at: datetime | None = Field(description="Null while the business is open")
    delete_after: datetime | None = Field(
        description="When the closed business and its data are deleted for good"
    )


class CloseRequest(BaseModel):
    confirm_name: str = Field(description="The business's exact name, typed to confirm")


def _state(context: TenantContext) -> Closure:
    closed_at = context.session.execute(
        text("SELECT closed_at FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return Closure(
        closed_at=closed_at,
        delete_after=None
        if closed_at is None
        else closed_at + timedelta(days=CLOSED_BUSINESS_GRACE_DAYS),
    )


def _audit(context: TenantContext, action: str) -> None:
    context.session.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, entity_type)
            VALUES (app.current_tenant_id(), 'user', app.current_user_id(), :action, 'tenant')
        """),
        {"action": action},
    )


@router.get("")
def get_closure(context: OwnerDep) -> Closure:
    return _state(context)


@router.post("")
def close_business(body: CloseRequest, context: OwnerDep) -> Closure:
    """Locks the business now. Its data is deleted after the grace period unless reopened."""
    db = context.session
    name = db.execute(
        text("SELECT name FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    if body.confirm_name.strip() != name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="name_mismatch"
        )
    changed = db.execute(
        text("""
            UPDATE app.tenants SET closed_at = now(), shifts_publish_auto = false
            WHERE id = app.current_tenant_id() AND closed_at IS NULL
        """)
    ).rowcount
    if not changed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_closed")
    _audit(context, "tenant.closed")
    events.record(db, "business_closed")
    return _state(context)


@router.delete("")
def reopen_business(context: OwnerDep) -> Closure:
    """Reopens a closed business, as long as it has not been deleted yet."""
    changed = context.session.execute(
        text("""
            UPDATE app.tenants SET closed_at = NULL
            WHERE id = app.current_tenant_id() AND closed_at IS NOT NULL
        """)
    ).rowcount
    if not changed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_closed")
    _audit(context, "tenant.reopened")
    return _state(context)
