"""Contact emails of the business and of each branch (round 5, F3).

Settings → "Business emails" and a branch's "Branch emails" read and write these. Each purpose
(main, inbox, billing, reply_to, notifications) can be set; an unset one falls back (see
app/messaging/contact_emails.py). A new address must be confirmed through a link emailed to it
before anything uses it."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import AnonymousSessionDep, TenantContext, require
from app.core.config import get_settings
from app.core.permissions import Permission
from app.core.signed_links import verify
from app.messaging.contact_emails import (
    PURPOSES,
    Purpose,
    confirm_token,
    confirmation_email,
    parse_subject,
    resolve_email_with_source,
)
from app.messaging.email import sender_from_settings

router = APIRouter(prefix="/contact-emails", tags=["contact-emails"])
public_router = APIRouter(tags=["contact-emails"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]
LocationQuery = Annotated[
    UUID | None, Query(description="A branch; leave out for the business's own")
]


class PurposeState(BaseModel):
    purpose: Purpose
    email: str | None = Field(description="What is set here (this business or branch), if any")
    verified: bool = Field(description="False while the confirmation link is still waiting")
    effective_email: str | None = Field(description="The address used for this purpose here")
    effective_source: Literal["branch", "business", "owner"]


class ContactEmails(BaseModel):
    location_id: UUID | None
    purposes: list[PurposeState]
    email_sent: bool | None = Field(
        default=None, description="Set after saving: whether a confirmation email went out"
    )


class ContactEmailSave(BaseModel):
    email: EmailStr


def _check_location(session: Session, location_id: UUID | None) -> None:
    if location_id is None:
        return
    found = session.execute(
        text("SELECT 1 FROM app.locations WHERE id = :id"), {"id": location_id}
    ).scalar()
    if found is None:
        raise not_found()


def _state(
    context: TenantContext, location_id: UUID | None, email_sent: bool | None = None
) -> ContactEmails:
    session = context.session
    rows = {
        row.purpose: row
        for row in session.execute(
            text("""
                SELECT purpose, email, verified_at FROM app.contact_emails
                WHERE tenant_id = :t AND location_id IS NOT DISTINCT FROM :l
            """),
            {"t": context.tenant_id, "l": location_id},
        )
    }
    states = []
    for purpose in PURPOSES:
        effective, source = resolve_email_with_source(
            session, context.tenant_id, purpose, location_id
        )
        row = rows.get(purpose)
        states.append(
            PurposeState(
                purpose=purpose,
                email=row.email if row else None,
                verified=row is not None and row.verified_at is not None,
                effective_email=effective,
                effective_source=source,
            )
        )
    return ContactEmails(location_id=location_id, purposes=states, email_sent=email_sent)


def _send_confirmation(context: TenantContext, purpose: str, row_id: UUID, email: str) -> bool:
    """Emails the confirmation link; False when no email provider is set up (or it failed)."""
    sender = sender_from_settings()
    if sender is None:
        return False
    session = context.session
    business = session.execute(
        text("SELECT name, locale FROM app.tenants WHERE id = :t"), {"t": context.tenant_id}
    ).one()
    token = confirm_token(context.tenant_id, row_id, email)
    try:
        sender.send(confirmation_email(email, business.name, purpose, token, business.locale))
    except Exception as error:  # saving the address must not fail because the provider did
        print(f"contact email confirmation to {email} failed: {error}")
        return False
    return True


@router.get("")
def get_contact_emails(context: SettingsDep, location_id: LocationQuery = None) -> ContactEmails:
    _check_location(context.session, location_id)
    return _state(context, location_id)


@router.put("/{purpose}")
def save_contact_email(
    purpose: Purpose,
    body: ContactEmailSave,
    context: SettingsDep,
    location_id: LocationQuery = None,
) -> ContactEmails:
    """Sets an address for one purpose. The owner's own sign-in email needs no confirmation;
    any other waits for its link. Setting the same address again does not reset it."""
    session = context.session
    _check_location(session, location_id)
    email = str(body.email).strip().lower()
    row = session.execute(
        text("""
            INSERT INTO app.contact_emails (tenant_id, location_id, purpose, email, verified_at)
            VALUES (
                :t, :l, :p, :e,
                CASE WHEN EXISTS (
                    SELECT 1 FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = :t AND m.role = 'owner' AND lower(u.email) = :e
                ) THEN now() END
            )
            ON CONFLICT (tenant_id, coalesce(location_id, '00000000-0000-0000-0000-000000000000'),
                         purpose)
            DO UPDATE SET
                verified_at = CASE WHEN app.contact_emails.email = EXCLUDED.email
                                   THEN app.contact_emails.verified_at
                                   ELSE EXCLUDED.verified_at END,
                email = EXCLUDED.email, updated_at = now()
            RETURNING id, verified_at
        """),
        {"t": context.tenant_id, "l": location_id, "p": purpose, "e": email},
    ).one()
    sent = None if row.verified_at else _send_confirmation(context, purpose, row.id, email)
    return _state(context, location_id, sent)


@router.post("/{purpose}/resend")
def resend_confirmation(
    purpose: Purpose, context: SettingsDep, location_id: LocationQuery = None
) -> ContactEmails:
    session = context.session
    _check_location(session, location_id)
    row = session.execute(
        text("""
            SELECT id, email, verified_at FROM app.contact_emails
            WHERE tenant_id = :t AND location_id IS NOT DISTINCT FROM :l AND purpose = :p
        """),
        {"t": context.tenant_id, "l": location_id, "p": purpose},
    ).first()
    if row is None:
        raise not_found()
    if row.verified_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_verified")
    sent = _send_confirmation(context, purpose, row.id, row.email)
    return _state(context, location_id, sent)


@router.delete("/{purpose}", status_code=status.HTTP_204_NO_CONTENT)
def clear_contact_email(
    purpose: Purpose, context: SettingsDep, location_id: LocationQuery = None
) -> Response:
    _check_location(context.session, location_id)
    context.session.execute(
        text("""
            DELETE FROM app.contact_emails
            WHERE tenant_id = :t AND location_id IS NOT DISTINCT FROM :l AND purpose = :p
        """),
        {"t": context.tenant_id, "l": location_id, "p": purpose},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.get("/public/contact-emails/confirm", include_in_schema=False)
def confirm_contact_email(token: str, session: AnonymousSessionDep) -> RedirectResponse:
    """The link in the confirmation email: marks the address verified, then shows the result on
    the web app. The signed token names the business, the row and the address, so a changed
    address needs a new link."""
    page = f"{get_settings().web_url.rstrip('/')}/email-confirmed"
    subject = verify(token)
    parsed = parse_subject(subject) if subject else None
    if parsed is None:
        return RedirectResponse(f"{page}?status=invalid")
    tenant_id, row_id, email = parsed
    confirmed = session.execute(
        text("SELECT app.confirm_contact_email(:t, :id, :e)"),
        {"t": tenant_id, "id": row_id, "e": email},
    ).scalar()
    return RedirectResponse(f"{page}?status={'ok' if confirmed else 'invalid'}")
