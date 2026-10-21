"""Two-step sign-in: which requests need the person to have entered an authenticator code.

Supabase puts the assurance level in the access token (`aal1`: password or link, `aal2`: also an
authenticator code). The MyBiz team always needs `aal2`. A business can require it of its whole
team (`tenants.require_mfa_for_staff`). For everyone else it is optional but warned about: an owner
or manager without a code can do sensitive actions only after confirming they understand the
risk (`app.mfa_risk_acknowledgements`, one row per version of the warning). That confirmation is
also the person's answer "I don't want two-step sign-in": the apps stop reminding them."""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import Permission
from app.core.rate_limit import client_address

AAL2 = "aal2"

# Raise it (to the date of the change) whenever the text of the warning changes: everyone then
# confirms again before their next sensitive action.
RISK_VERSION = "2026-10-21"
USER_AGENT_LIMIT = 200

# Where the person confirmed: their security settings, the "I don't want two-step sign-in" choice
# of the account status, or the window that opens when a sensitive action is refused.
RiskSource = Literal["settings", "opt_out", "sensitive_action"]

# Seeing ID numbers, pay, the team's roles, provider secrets and settings, personal-data exports.
SENSITIVE_PERMISSIONS = frozenset(
    {
        Permission.IDENTITY_READ,
        Permission.CLIENTS_PRIVACY,
        Permission.PAYROLL_READ,
        Permission.PAYROLL_MANAGE,
        Permission.PAYROLL_APPROVE,
        Permission.STAFF_MANAGE,
        Permission.BUSINESS_SETTINGS,
        Permission.MIGRATION_MANAGE,
    }
)


def mfa_required() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="mfa_required")


def require_aal2(aal: str) -> None:
    """The MyBiz team's gate: always on outside local development."""
    if get_settings().mfa_on and aal != AAL2:
        raise mfa_required()


def mfa_risk_not_acknowledged() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="mfa_risk_ack_required")


def has_acknowledged_risk(session: Session) -> bool:
    return bool(
        session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM app.mfa_risk_acknowledgements
                    WHERE user_id = app.current_user_id() AND version = :version
                )
            """),
            {"version": RISK_VERSION},
        ).scalar_one()
    )


def check_sensitive_action(session: Session, aal: str) -> None:
    """Owners' and managers' sensitive actions: a code, or the confirmed warning. Refuses with
    `mfa_risk_ack_required`, which the apps answer by showing the warning."""
    settings = get_settings()
    if not settings.mfa_on or aal == AAL2 or has_acknowledged_risk(session):
        return
    raise mfa_risk_not_acknowledged()


def record_risk_acknowledgement(
    session: Session, request: Request, user_id: UUID, source: RiskSource = "settings"
) -> None:
    """Stores that the person read the warning: when, from where and in which screen. Doing it
    twice is a no-op: the first confirmation of a version is the one kept."""
    settings = get_settings()
    address = client_address(
        request,
        settings.trust_forwarded_for,
        settings.internal_token.get_secret_value() if settings.internal_token else None,
    )
    session.execute(
        text("""
            INSERT INTO app.mfa_risk_acknowledgements
                (user_id, version, ip_address, user_agent, source)
            VALUES (:user, :version, :ip, :agent, :source)
            ON CONFLICT DO NOTHING
        """),
        {
            "user": user_id,
            "version": RISK_VERSION,
            "ip": address,
            "agent": request.headers.get("user-agent", "")[:USER_AGENT_LIMIT],
            "source": source,
        },
    )
