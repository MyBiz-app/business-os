"""Which phone alerts the business owner wants (app sweep slice 14, improvement B14).

The alerts themselves are sent by the hourly job `alert-owners` (app/messaging/owner_alerts.py).
Here an owner reads the list and switches a kind on or off for the business they are in. A kind
with no saved choice is on."""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import TenantDep, UserDep
from app.messaging.owner_alerts import KINDS, QUIET_FROM_HOUR, QUIET_UNTIL_HOUR

router = APIRouter(prefix="/owner-alerts", tags=["account"])

AlertKind = Literal[
    "booking_new", "booking_cancelled", "waitlist_joined", "client_joined", "lead_new"
]


class AlertSetting(BaseModel):
    kind: AlertKind
    enabled: bool


class AlertSettings(BaseModel):
    kinds: list[AlertSetting]
    quiet_from_hour: int
    quiet_until_hour: int


class AlertChoice(BaseModel):
    enabled: bool


def _owner_only(context: TenantDep) -> None:
    if context.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def _settings(context: TenantDep, user: UserDep) -> AlertSettings:
    off = set(
        context.session.execute(
            text("SELECT kind FROM app.owner_push_prefs WHERE user_id = :u AND NOT enabled"),
            {"u": user.id},
        ).scalars()
    )
    return AlertSettings(
        kinds=[AlertSetting(kind=kind, enabled=kind not in off) for kind in KINDS],  # type: ignore[arg-type]
        quiet_from_hour=QUIET_FROM_HOUR,
        quiet_until_hour=QUIET_UNTIL_HOUR,
    )


@router.get("", response_model=AlertSettings)
def get_alert_settings(context: TenantDep, user: UserDep) -> AlertSettings:
    """The alert kinds and whether each is on for this owner in this business."""
    _owner_only(context)
    return _settings(context, user)


@router.put("/{kind}", response_model=AlertSettings)
def set_alert(
    kind: AlertKind, body: AlertChoice, context: TenantDep, user: UserDep
) -> AlertSettings:
    """Switches one alert kind on or off for this owner in this business."""
    _owner_only(context)
    context.session.execute(
        text("""
            INSERT INTO app.owner_push_prefs (tenant_id, user_id, kind, enabled)
            VALUES (:t, :u, :kind, :enabled)
            ON CONFLICT (tenant_id, user_id, kind) DO UPDATE SET enabled = :enabled
        """),
        {"t": context.tenant_id, "u": user.id, "kind": kind, "enabled": body.enabled},
    )
    return _settings(context, user)
