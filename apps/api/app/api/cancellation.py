"""The business's cancellation policy, giving a client's visit back, and what the client sees.

The policy has three layers and the most specific wins: the plan the booking uses, then the
service, then the business (one window each for a class, a personal session and a court or room).
The database resolves it (`app.cancellation_terms`, migration 0136) so cancelling, marking a
no-show and the preview a client sees can never disagree. A fee for a late cancellation is built
into the model but kept off until payments are on, so it cannot be chosen yet."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import ClientDep, TenantContext, TenantDep, ensure_branch_visible, require
from app.api.freeze_requests import local_today
from app.catalog.cancellation import defaults_for
from app.catalog.verticals import CATALOG
from app.core.audit import record
from app.core.permissions import Permission
from app.messaging.email import load_all_messages
from app.messaging.notifications import notify, session_snapshot

router = APIRouter(tags=["bookings"])
client_router = APIRouter(prefix="/client", tags=["client"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]
SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]

# What a late cancellation or a no-show means. "fee" exists in the database but cannot be chosen
# until payments are switched on (#46).
Outcome = Literal["counts", "recorded"]
StoredOutcome = Literal["counts", "recorded", "fee"]
Minutes = Annotated[int, Field(ge=0, le=10080, description="Up to a week")]
LOCALES = ("he", "en")


class Terms(BaseModel):
    late_outcome: Outcome = Field(
        default="counts",
        description="Cancelling inside the window: a used visit (counts) or only noted (recorded)",
    )
    no_show_outcome: Outcome = Field(
        default="counts", description="Not coming: a used visit (counts) or only noted (recorded)"
    )
    no_show_limit: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="No-shows in 30 days after which the app stops booking the client; empty: off",
    )


class BusinessPolicy(Terms):
    group_minutes: Minutes = Field(description="Free cancellation before a group class")
    personal_minutes: Minutes = Field(description="... before a personal session or appointment")
    resource_minutes: Minutes = Field(description="... before a court or room reservation")


class BusinessPolicyView(BusinessPolicy):
    configured: bool = Field(
        description="False until the business saves its policy (the category's suggestion, or "
        "its one old window, applies until then)"
    )


class OverridePolicy(Terms):
    free_minutes: Minutes = Field(description="Free cancellation before the session")


class ServiceOverride(BaseModel):
    service_id: UUID
    name: str
    policy: OverridePolicy | None


class PlanOverride(BaseModel):
    plan_id: UUID
    name: str
    policy: OverridePolicy | None


class PolicyText(BaseModel):
    he: str
    en: str


class PolicyOverview(BaseModel):
    business: BusinessPolicyView
    suggested: BusinessPolicy = Field(description="The default for this kind of business")
    services: list[ServiceOverride]
    plans: list[PlanOverride]
    text: PolicyText = Field(description="What clients are told, from the saved policy")


class ClientPolicy(BaseModel):
    text: PolicyText


class WaiveBody(BaseModel):
    reason: str = Field(min_length=3, max_length=300, description="Required; kept with who/when")

    @field_validator("reason", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return blank_to_none(value) if isinstance(value, str) else value


class Waiver(BaseModel):
    booking_id: UUID
    service_name: str
    starts_at: dt.datetime
    waived_at: dt.datetime
    waived_by_name: str | None
    reason: str | None


class WaiverSummary(BaseModel):
    this_year: int = Field(description="Visits given back to this client in the current year")
    items: list[Waiver] = Field(description="Newest first, at most 50")


class CancelPreview(BaseModel):
    booking_id: UUID
    free_until: dt.datetime = Field(description="Cancelling before this moment is free")
    late: bool = Field(description="Cancelling now is inside the window")
    outcome: Literal["free", "counts", "recorded"] = Field(
        description="What cancelling now does: nothing, uses a visit, or is only noted"
    )
    plan_name: str | None
    plan_kind: Literal["membership", "punch_card"] | None
    period_quota: int | None = Field(description="Visits per week or month the plan allows")
    period_unit: Literal["week", "month"] | None
    period_used: int | None = Field(description="Visits already counted in that period")


# --- Reading and saving the policy -------------------------------------------------------------


def _suggested(db: Session) -> BusinessPolicy:
    vertical = db.execute(
        text("SELECT vertical FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    defaults = defaults_for(CATALOG[vertical].category)
    return BusinessPolicy(
        group_minutes=defaults.group_minutes,
        personal_minutes=defaults.personal_minutes,
        resource_minutes=defaults.resource_minutes,
        late_outcome=defaults.late_outcome,  # type: ignore[arg-type]
        no_show_outcome=defaults.no_show_outcome,  # type: ignore[arg-type]
    )


def _outcome(value: str) -> str:
    return "recorded" if value == "fee" else value  # a fee is never charged yet


def load_business_policy(db: Session) -> BusinessPolicyView:
    row = (
        db.execute(
            text("""
                SELECT group_minutes, personal_minutes, resource_minutes, late_outcome,
                       no_show_outcome, no_show_limit, confirmed AS configured
                FROM app.cancellation_policies WHERE scope = 'business'
            """)
        )
        .mappings()
        .first()
    )
    if row is None:  # the one old window, and a late cancellation uses the visit
        window = db.execute(
            text(
                "SELECT cancellation_window_minutes FROM app.tenants"
                " WHERE id = app.current_tenant_id()"
            )
        ).scalar_one()
        return BusinessPolicyView(
            group_minutes=window,
            personal_minutes=window,
            resource_minutes=window,
            configured=False,
        )
    data = dict(row)
    data["late_outcome"] = _outcome(data["late_outcome"])
    data["no_show_outcome"] = _outcome(data["no_show_outcome"])
    return BusinessPolicyView(**data)


def _duration(minutes: int, messages: dict[str, Any]) -> str:
    unit = messages["units"]
    if minutes == 0:
        return unit["none"]
    if minutes % 1440 == 0:
        days = minutes // 1440
        return unit["day"] if days == 1 else unit["days"].replace("{n}", str(days))
    if minutes % 60 == 0:
        hours = minutes // 60
        return unit["hour"] if hours == 1 else unit["hours"].replace("{n}", str(hours))
    return unit["minutes"].replace("{n}", str(minutes))


def policy_text(policy: BusinessPolicy, locale: str) -> str:
    """The policy in words, for clients (the business page and the first sign-up)."""
    messages = load_all_messages(locale)["cancellationPolicy"]
    windows = {
        "group": policy.group_minutes,
        "personal": policy.personal_minutes,
        "resource": policy.resource_minutes,
    }
    lines: list[str] = []
    if len(set(windows.values())) == 1:
        lines.append(messages["free"].replace("{time}", _duration(policy.group_minutes, messages)))
    else:
        for kind, minutes in windows.items():
            lines.append(
                messages["freeFor"]
                .replace("{kind}", messages["kinds"][kind])
                .replace("{time}", _duration(minutes, messages))
            )
    lines.append(messages["late"][policy.late_outcome])
    lines.append(messages["noShow"][policy.no_show_outcome])
    if policy.no_show_limit:
        lines.append(messages["limit"].replace("{n}", str(policy.no_show_limit)))
    return " ".join(lines)


def both_texts(policy: BusinessPolicy) -> PolicyText:
    return PolicyText(he=policy_text(policy, "he"), en=policy_text(policy, "en"))


def _overview(db: Session) -> PolicyOverview:
    business = load_business_policy(db)
    services = db.execute(
        text("""
            SELECT sv.id AS service_id, sv.name, cp.free_minutes, cp.late_outcome,
                   cp.no_show_outcome, cp.no_show_limit
            FROM app.services sv
            LEFT JOIN app.cancellation_policies cp
                ON cp.scope = 'service' AND cp.service_id = sv.id
            WHERE sv.active ORDER BY sv.name, sv.id
        """)
    ).mappings()
    plans = db.execute(
        text("""
            SELECT p.id AS plan_id, p.name, cp.free_minutes, cp.late_outcome,
                   cp.no_show_outcome, cp.no_show_limit
            FROM app.plans p
            LEFT JOIN app.cancellation_policies cp ON cp.scope = 'plan' AND cp.plan_id = p.id
            WHERE p.active ORDER BY p.name, p.id
        """)
    ).mappings()

    def override(row: Any) -> OverridePolicy | None:
        if row["free_minutes"] is None:
            return None
        return OverridePolicy(
            free_minutes=row["free_minutes"],
            late_outcome=_outcome(row["late_outcome"]),  # type: ignore[arg-type]
            no_show_outcome=_outcome(row["no_show_outcome"]),  # type: ignore[arg-type]
            no_show_limit=row["no_show_limit"],
        )

    return PolicyOverview(
        business=business,
        suggested=_suggested(db),
        services=[
            ServiceOverride(service_id=r["service_id"], name=r["name"], policy=override(r))
            for r in services
        ],
        plans=[
            PlanOverride(plan_id=r["plan_id"], name=r["name"], policy=override(r)) for r in plans
        ],
        text=both_texts(business),
    )


@router.get("/cancellation-policy")
def get_policy(context: TenantDep) -> PolicyOverview:
    return _overview(context.session)


@router.put("/cancellation-policy")
def set_policy(body: BusinessPolicy, context: SettingsDep) -> PolicyOverview:
    db = context.session
    db.execute(
        text("""
            INSERT INTO app.cancellation_policies
                (tenant_id, scope, group_minutes, personal_minutes, resource_minutes,
                 late_outcome, no_show_outcome, no_show_limit, confirmed)
            VALUES (:tenant_id, 'business', :group_minutes, :personal_minutes, :resource_minutes,
                    :late_outcome, :no_show_outcome, :no_show_limit, true)
            ON CONFLICT (tenant_id) WHERE scope = 'business' DO UPDATE SET
                confirmed = true,
                group_minutes = EXCLUDED.group_minutes,
                personal_minutes = EXCLUDED.personal_minutes,
                resource_minutes = EXCLUDED.resource_minutes,
                late_outcome = EXCLUDED.late_outcome,
                no_show_outcome = EXCLUDED.no_show_outcome,
                no_show_limit = EXCLUDED.no_show_limit, updated_at = now()
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id},
    )
    # Places that show one window (invitations, the client app) keep following the class window.
    db.execute(
        text("UPDATE app.tenants SET cancellation_window_minutes = :minutes WHERE id = :id"),
        {"minutes": body.group_minutes, "id": context.tenant_id},
    )
    record(db, "cancellation_policy.update")
    return _overview(db)


def _save_override(
    db: Session, context: TenantContext, scope: str, target: UUID, body: OverridePolicy
) -> None:
    column = "service_id" if scope == "service" else "plan_id"
    table = "app.services" if scope == "service" else "app.plans"
    if db.execute(text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": target}).first() is None:
        raise not_found()
    db.execute(
        text(f"""
            INSERT INTO app.cancellation_policies
                (tenant_id, scope, {column}, free_minutes, late_outcome, no_show_outcome,
                 no_show_limit)
            VALUES (:tenant_id, :scope, :target, :free_minutes, :late_outcome, :no_show_outcome,
                    :no_show_limit)
            ON CONFLICT (tenant_id, {column}) WHERE scope = :scope DO UPDATE SET
                free_minutes = EXCLUDED.free_minutes, late_outcome = EXCLUDED.late_outcome,
                no_show_outcome = EXCLUDED.no_show_outcome,
                no_show_limit = EXCLUDED.no_show_limit, updated_at = now()
        """),
        {**body.model_dump(), "tenant_id": context.tenant_id, "scope": scope, "target": target},
    )
    record(db, f"cancellation_policy.{scope}", entity_type=scope, entity_id=target)


def _remove_override(db: Session, scope: str, target: UUID) -> None:
    column = "service_id" if scope == "service" else "plan_id"
    db.execute(
        text(f"DELETE FROM app.cancellation_policies WHERE scope = :scope AND {column} = :id"),
        {"scope": scope, "id": target},
    )
    record(db, f"cancellation_policy.{scope}_removed", entity_type=scope, entity_id=target)


@router.put("/services/{service_id}/cancellation-policy")
def set_service_policy(
    service_id: UUID, body: OverridePolicy, context: SettingsDep
) -> PolicyOverview:
    """This service uses its own terms instead of the business's."""
    _save_override(context.session, context, "service", service_id, body)
    return _overview(context.session)


@router.delete("/services/{service_id}/cancellation-policy")
def clear_service_policy(service_id: UUID, context: SettingsDep) -> PolicyOverview:
    _remove_override(context.session, "service", service_id)
    return _overview(context.session)


@router.put("/plans/{plan_id}/cancellation-policy")
def set_plan_policy(plan_id: UUID, body: OverridePolicy, context: SettingsDep) -> PolicyOverview:
    """Bookings that use this plan follow its terms (the most specific layer)."""
    _save_override(context.session, context, "plan", plan_id, body)
    return _overview(context.session)


@router.delete("/plans/{plan_id}/cancellation-policy")
def clear_plan_policy(plan_id: UUID, context: SettingsDep) -> PolicyOverview:
    _remove_override(context.session, "plan", plan_id)
    return _overview(context.session)


# --- Giving a visit back -----------------------------------------------------------------------


@router.post("/bookings/{booking_id}/waive")
def waive(booking_id: UUID, body: WaiveBody, context: SalesDep) -> dict[str, bool]:
    """An exception: the client keeps the visit a late cancellation or a no-show used up. Needs
    a reason; who and when are kept, and the client is told."""
    db = context.session
    booking = (
        db.execute(
            text("""
                SELECT b.client_id, b.session_id, s.location_id
                FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
                WHERE b.id = :id
            """),
            {"id": booking_id},
        )
        .mappings()
        .first()
    )
    if booking is None:
        raise not_found()
    ensure_branch_visible(context, booking["location_id"])
    returned = db.execute(
        text("""
            UPDATE app.bookings
            SET credit_released = true, waived_by = app.current_user_id(), waived_at = now(),
                waive_reason = :reason, updated_at = now()
            WHERE id = :id AND NOT credit_released
              AND ((status = 'cancelled' AND late_cancel) OR status = 'no_show')
            RETURNING id
        """),
        {"id": booking_id, "reason": body.reason},
    ).first()
    if returned is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="nothing_to_return")
    notify(
        db,
        context.tenant_id,
        [booking["client_id"]],
        "credit_returned",
        session_snapshot(db, booking["session_id"]),
    )
    record(db, "booking.waive", entity_type="booking", entity_id=booking_id)
    return {"ok": True}


@router.get("/clients/{client_id}/waivers")
def client_waivers(client_id: UUID, context: ClientsReadDep) -> WaiverSummary:
    """The visits given back to a client, and how many this year, so it does not become a habit."""
    db = context.session
    year = local_today(db).year
    rows = (
        db.execute(
            text("""
                SELECT b.id AS booking_id, sv.name AS service_name, s.starts_at, b.waived_at,
                       u.full_name AS waived_by_name, b.waive_reason AS reason
                FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id
                JOIN app.services sv ON sv.id = s.service_id
                LEFT JOIN app.users u ON u.id = b.waived_by
                WHERE b.client_id = :id AND b.waived_at IS NOT NULL
                ORDER BY b.waived_at DESC LIMIT 50
            """),
            {"id": client_id},
        )
        .mappings()
        .all()
    )
    this_year = db.execute(
        text("""
            SELECT count(*) FROM app.bookings b JOIN app.tenants t ON t.id = b.tenant_id
            WHERE b.client_id = :id AND b.waived_at IS NOT NULL
              AND extract(year FROM b.waived_at AT TIME ZONE t.time_zone) = :year
        """),
        {"id": client_id, "year": year},
    ).scalar_one()
    return WaiverSummary(this_year=this_year, items=[Waiver(**row) for row in rows])


def ensure_within_no_show_limit(db: Session, client_id: UUID) -> None:
    """Booking from the app pauses for a client who did not come too many times lately, if the
    business set a limit (off by default). Staff can still book them."""
    limit = db.execute(
        text("SELECT no_show_limit FROM app.cancellation_policies WHERE scope = 'business'")
    ).scalar()
    if not limit:
        return
    missed = db.execute(
        text("""
            SELECT count(*) FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
            WHERE b.client_id = :id AND b.status = 'no_show'
              AND s.starts_at > now() - interval '30 days'
        """),
        {"id": client_id},
    ).scalar_one()
    if missed >= limit:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_show_limit")


# --- The client's side -------------------------------------------------------------------------


@client_router.get("/cancellation-policy")
def my_policy(context: ClientDep) -> ClientPolicy:
    """The business's rules in words, for the business page and the first sign-up."""
    db = context.session
    row = (
        db.execute(
            text("""
                SELECT group_minutes, personal_minutes, resource_minutes, late_outcome,
                       no_show_outcome, no_show_limit
                FROM app.cancellation_policies WHERE scope = 'business'
            """)
        )
        .mappings()
        .first()
    )
    if row is None:
        window = db.execute(
            text("SELECT cancellation_window_minutes FROM app.tenants WHERE id = :id"),
            {"id": context.tenant_id},
        ).scalar_one()
        policy = BusinessPolicy(
            group_minutes=window, personal_minutes=window, resource_minutes=window
        )
    else:
        data = dict(row)
        data["late_outcome"] = _outcome(data["late_outcome"])
        data["no_show_outcome"] = _outcome(data["no_show_outcome"])
        policy = BusinessPolicy(**data)
    return ClientPolicy(text=both_texts(policy))


@client_router.get("/bookings/{booking_id}/cancel-preview")
def cancel_preview(booking_id: UUID, context: ClientDep) -> CancelPreview:
    """What cancelling this booking now would do, shown before the client confirms."""
    row = (
        context.session.execute(
            text("""
                SELECT b.id AS booking_id, b.status, s.starts_at, ct.free_minutes,
                       ct.late_outcome, e.name AS plan_name, e.kind AS plan_kind,
                       e.period_quota, e.period_unit,
                       CASE WHEN e.period_unit IS NOT NULL THEN
                           app.quota_used(e.id, (s.starts_at AT TIME ZONE t.time_zone)::date)
                       END AS period_used
                FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id
                JOIN app.tenants t ON t.id = b.tenant_id
                LEFT JOIN app.entitlements e ON e.id = b.entitlement_id
                CROSS JOIN LATERAL app.cancellation_terms(b.session_id, b.entitlement_id) ct
                WHERE b.id = :id AND b.status <> 'cancelled'
            """),
            {"id": booking_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    free_until = row["starts_at"] - dt.timedelta(minutes=row["free_minutes"])
    late = row["status"] != "waitlisted" and dt.datetime.now(dt.UTC) > free_until
    outcome = "free" if not late else _outcome(row["late_outcome"])
    return CancelPreview(
        booking_id=row["booking_id"],
        free_until=free_until,
        late=late,
        outcome=outcome,  # type: ignore[arg-type]
        plan_name=row["plan_name"],
        plan_kind=row["plan_kind"],
        period_quota=row["period_quota"],
        period_unit=row["period_unit"],
        period_used=row["period_used"],
    )
