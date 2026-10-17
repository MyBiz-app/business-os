"""Two-step sign-in: which requests need the person to have entered an authenticator code.

Supabase puts the assurance level in the access token (`aal1`: password or link, `aal2`: also an
authenticator code). The MyBiz team always needs `aal2`. A business can require it of its whole
team (`tenants.require_mfa_for_staff`), and sensitive actions of owners and managers need it from
`API_MFA_REQUIRED_FROM` on (a grace period for businesses that already exist)."""

import datetime as dt

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.permissions import Permission

AAL2 = "aal2"

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


def sensitive_action_needs_mfa(aal: str, today: dt.date | None = None) -> bool:
    """Owners' and managers' sensitive actions, once the grace period is over."""
    settings = get_settings()
    if not settings.mfa_on or aal == AAL2:
        return False
    start = settings.mfa_required_from
    return start is None or (today or dt.date.today()) >= start
