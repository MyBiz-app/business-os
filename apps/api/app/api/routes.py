from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, TenantDep, UserDep
from app.api.modules import check_selection, set_modules
from app.api.schemas import Me, Membership, Tenant, TenantCreate
from app.core.db import set_tenant
from app.modules import PRESETS
from app.permissions import effective_permissions
from app.verticals import VERTICAL_PACKS

router = APIRouter()


def ensure_profile(session: Session, user_id: UUID, email: str) -> None:
    """Creates the user's profile on first use; the email follows the identity provider."""
    session.execute(
        text("""
            INSERT INTO app.users (id, email) VALUES (:id, :email)
            ON CONFLICT (id) DO UPDATE SET email = excluded.email, updated_at = now()
                WHERE app.users.email IS DISTINCT FROM excluded.email
        """),
        {"id": user_id, "email": email},
    )


def load_current_tenant(session: Session) -> Tenant:
    row = (
        session.execute(
            text("""
                SELECT t.id, t.name, t.vertical, t.locale, t.time_zone, t.currency,
                       t.primary_color, t.cancellation_window_minutes, t.booking_requires_plan,
                       t.requires_health_declaration, t.online_sales,
                       t.join_code, m.role, r.name AS custom_role_name,
                       r.permissions AS custom_permissions,
                       coalesce((SELECT array_agg(tm.module_key ORDER BY tm.module_key)
                                 FROM app.tenant_modules tm WHERE tm.tenant_id = t.id), '{}')
                           AS modules,
                       CASE WHEN t.logo IS NULL THEN NULL
                            ELSE '/public/tenants/' || t.id || '/logo?v='
                                 || extract(epoch FROM t.logo_updated_at)::bigint END AS logo_url
                FROM app.tenants t
                JOIN app.tenant_members m
                    ON m.tenant_id = t.id AND m.user_id = app.current_user_id()
                LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
                WHERE t.id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    data = dict(row)
    data["permissions"] = sorted(
        effective_permissions(data["role"], data.pop("custom_permissions"))
    )
    return Tenant.model_validate(data)


def apply_vertical_pack(
    session: Session | Connection, tenant_id: UUID, vertical: str, locale: str, currency: str
) -> None:
    """Gives a new business its vertical's defaults: booking policy and starter plans."""
    pack = VERTICAL_PACKS[vertical]
    session.execute(
        text("""
            UPDATE app.tenants
            SET cancellation_window_minutes = :minutes, booking_requires_plan = :requires_plan,
                requires_health_declaration = :requires_health
            WHERE id = :id
        """),
        {
            "minutes": pack.cancellation_window_minutes,
            "requires_plan": pack.booking_requires_plan,
            "requires_health": pack.requires_health_declaration,
            "id": tenant_id,
        },
    )
    for plan in pack.default_plans:
        session.execute(
            text("""
                INSERT INTO app.plans
                    (tenant_id, name, kind, validity_days, credits, price_amount, price_currency)
                VALUES (:tenant_id, :name, :kind, :validity_days, :credits, :price, :currency)
            """),
            {
                "tenant_id": tenant_id,
                "name": plan.names.get(locale, plan.names["en"]),
                "kind": plan.kind,
                "validity_days": plan.validity_days,
                "credits": plan.credits,
                "price": plan.prices.get(currency, 0),
                "currency": currency,
            },
        )


@router.get("/me", tags=["account"])
def get_me(user: UserDep, session: SessionDep) -> Me:
    ensure_profile(session, user.id, user.email)
    profile = (
        session.execute(
            text("""
                SELECT id, email, full_name, locale, app.is_platform_admin() AS platform_admin
                FROM app.users WHERE id = :id
            """),
            {"id": user.id},
        )
        .mappings()
        .one()
    )
    memberships = session.execute(
        text("""
            SELECT m.tenant_id, t.name AS tenant_name, m.role
            FROM app.tenant_members m
            JOIN app.tenants t ON t.id = m.tenant_id
            WHERE m.user_id = app.current_user_id()
            ORDER BY t.created_at
        """)
    ).mappings()
    return Me(**profile, memberships=[Membership.model_validate(dict(m)) for m in memberships])


@router.post("/tenants", status_code=status.HTTP_201_CREATED, tags=["tenants"])
def create_tenant(body: TenantCreate, user: UserDep, session: SessionDep) -> Tenant:
    ensure_profile(session, user.id, user.email)
    modules = (
        body.modules
        if body.modules is not None
        else dict.fromkeys(PRESETS[VERTICAL_PACKS[body.vertical].default_preset], 1)
    )
    check_selection(modules)
    tenant_id: UUID = session.execute(
        text("SELECT app.create_tenant(:name, :vertical, :locale, :time_zone, :currency)"),
        body.model_dump(exclude={"modules"}),
    ).scalar_one()
    set_tenant(session, tenant_id)
    apply_vertical_pack(session, tenant_id, body.vertical, body.locale, body.currency)
    set_modules(session, tenant_id, modules)
    return load_current_tenant(session)


@router.get("/tenants/current", tags=["tenants"])
def get_current_tenant(context: TenantDep) -> Tenant:
    return load_current_tenant(context.session)
