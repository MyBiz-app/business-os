from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.api.common import set_clause
from app.api.deps import SessionDep, TenantDep, UserDep
from app.api.modules import check_selection, set_modules
from app.api.schemas import (
    Me,
    Membership,
    Palette,
    PaletteColors,
    SupportAccess,
    Tenant,
    TenantCreate,
)
from app.catalog.verticals import VERTICAL_PACKS
from app.commerce.modules import PRESETS
from app.core.db import set_tenant
from app.core.permissions import Permission, effective_permissions
from app.messaging.email import load_all_messages

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
                       t.requires_health_declaration, t.online_sales, t.resource_payment,
                       t.join_code,
                       coalesce(m.role,
                                CASE WHEN app.support_tenant_id() IS NOT NULL THEN 'support'
                                     ELSE 'platform' END) AS role,
                       r.name AS custom_role_name,
                       r.permissions AS custom_permissions,
                       coalesce((SELECT array_agg(tm.module_key ORDER BY tm.module_key)
                                 FROM app.tenant_modules tm WHERE tm.tenant_id = t.id), '{}')
                           AS modules,
                       CASE WHEN t.logo IS NULL THEN NULL
                            ELSE '/public/tenants/' || t.id || '/logo?v='
                                 || extract(epoch FROM t.logo_updated_at)::bigint END AS logo_url,
                       CASE WHEN t.cover IS NULL THEN NULL
                            ELSE '/tenants/current/cover?v='
                                 || extract(epoch FROM t.cover_updated_at)::bigint END AS cover_url,
                       t.legal_entity_type, t.business_number
                FROM app.tenants t
                LEFT JOIN app.tenant_members m
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
    # The registration number is for the people who manage the business, not the whole team.
    if Permission.BUSINESS_SETTINGS.value not in data["permissions"]:
        data["legal_entity_type"] = data["business_number"] = None
    return Tenant.model_validate(data)


def apply_vertical_pack(
    session: Session | Connection, tenant_id: UUID, vertical: str, locale: str, currency: str
) -> None:
    """Gives a new business its vertical's defaults: booking policy, services and plans."""
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
    for service in pack.default_services:
        resource = service.booking_mode == "resource"  # by the hour: prices are per hour
        session.execute(
            text("""
                INSERT INTO app.services
                    (tenant_id, name, duration_minutes, capacity, booking_mode, price_amount,
                     price_currency, color, min_minutes, max_minutes, step_minutes,
                     price_per_hour, on_site, travel_minutes)
                VALUES (:tenant_id, :name, :minutes, :capacity, :mode, :price, :currency, :color,
                        :min_minutes, :max_minutes, :step_minutes, :per_hour, :on_site,
                        :travel_minutes)
            """),
            {
                "tenant_id": tenant_id,
                "name": service.names.get(locale, service.names["en"]),
                "minutes": service.duration_minutes,
                "capacity": service.capacity,
                "mode": service.booking_mode,
                "price": service.prices.get(currency, 0),
                "currency": currency,
                "color": service.color,
                "min_minutes": service.duration_minutes if resource else None,
                "max_minutes": service.max_minutes if resource else None,
                "step_minutes": service.step_minutes if resource else None,
                "per_hour": service.prices.get(currency, 0) if resource else None,
                "on_site": service.on_site,
                "travel_minutes": service.travel_minutes if service.on_site else 0,
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


def apply_vertical_rooms(
    session: Session | Connection, tenant_id: UUID, vertical: str, locale: str
) -> None:
    """Gives a new business its vertical's starter courts and rooms (once its branches exist):
    in the main branch, for rent every day, serving the business's resource services."""
    pack = VERTICAL_PACKS[vertical]
    if not pack.default_rooms:
        return
    location_id = session.execute(
        text("SELECT id FROM app.locations WHERE tenant_id = :t ORDER BY created_at, id LIMIT 1"),
        {"t": tenant_id},
    ).scalar_one()
    services = (
        session.execute(
            text("SELECT id FROM app.services WHERE tenant_id = :t AND booking_mode = 'resource'"),
            {"t": tenant_id},
        )
        .scalars()
        .all()
    )
    for room in pack.default_rooms:
        room_id = session.execute(
            text("""
                INSERT INTO app.rooms (tenant_id, location_id, name, capacity, bookable)
                VALUES (:t, :location, :name, :capacity, true) RETURNING id
            """),
            {
                "t": tenant_id,
                "location": location_id,
                "name": room.names.get(locale, room.names["en"]),
                "capacity": room.capacity,
            },
        ).scalar_one()
        session.execute(
            text("""
                INSERT INTO app.room_hours (tenant_id, room_id, weekday, starts, ends)
                SELECT :t, :room, d, CAST(:opens AS time), CAST(:closes AS time)
                FROM generate_series(0, 6) d
            """),
            {"t": tenant_id, "room": room_id, "opens": room.opens, "closes": room.closes},
        )
        for service_id in services:
            session.execute(
                text("""
                    INSERT INTO app.service_rooms (tenant_id, service_id, room_id)
                    VALUES (:t, :service, :room)
                """),
                {"t": tenant_id, "service": service_id, "room": room_id},
            )


@router.get("/me", tags=["account"])
def get_me(user: UserDep, session: SessionDep) -> Me:
    ensure_profile(session, user.id, user.email)
    profile = (
        session.execute(
            text("""
                SELECT id, email, full_name, locale, app.is_platform_admin() AS platform_admin,
                       phone, palette,
                       CASE WHEN palette_background IS NULL THEN NULL
                            ELSE jsonb_build_object('background', palette_background,
                                                    'text', palette_text,
                                                    'accent', palette_accent)
                       END AS palette_colors,
                       CASE WHEN avatar_updated_at IS NULL THEN NULL
                            ELSE '/me/avatar?v=' || extract(epoch FROM avatar_updated_at)::bigint
                       END AS avatar_url
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
    support = session.execute(
        text("SELECT tenant_id, tenant_name, expires_at FROM app.my_support_grants()")
    ).mappings()
    return Me(
        **profile,
        memberships=[Membership.model_validate(dict(m)) for m in memberships],
        support_access=[SupportAccess.model_validate(dict(g)) for g in support],
    )


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
    create_first_branches(session, tenant_id, body.locale, 1 + modules.get("extra_location", 0))
    apply_vertical_rooms(session, tenant_id, body.vertical, body.locale)
    return load_current_tenant(session)


def create_first_branches(
    session: Session | Connection, tenant_id: UUID, locale: str, count: int
) -> None:
    """A business starts with its main branch, plus the extra branches chosen at sign-up
    (renamed later). The extra-branch charge then follows the active branches."""
    names = load_all_messages(locale)["locations"]
    for number in range(1, count + 1):
        name = (
            names["mainBranch"]
            if number == 1
            else names["branchNumber"].replace("{number}", str(number))
        )
        session.execute(
            # clock_timestamp keeps them in order (the main branch first) within one transaction
            text("""
                INSERT INTO app.locations (tenant_id, name, created_at)
                VALUES (:t, :name, clock_timestamp())
            """),
            {"t": tenant_id, "name": name},
        )


@router.get("/tenants/current", tags=["tenants"])
def get_current_tenant(context: TenantDep) -> Tenant:
    return load_current_tenant(context.session)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+()\- ]*$")
    palette: Palette | None = None
    palette_colors: PaletteColors | None = None

    @model_validator(mode="after")
    def custom_needs_colors(self) -> "ProfileUpdate":
        if self.palette == "custom" and self.palette_colors is None:
            raise ValueError("the custom palette needs its three colors")
        return self

    @field_validator("full_name", "phone", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


@router.patch("/me", tags=["account"])
def update_me(body: ProfileUpdate, user: UserDep, session: SessionDep) -> Me:
    """The signed-in person's own profile: the name the team, clients and reports see, a phone
    number for the team, and their color palette. Fields left out stay as they are."""
    ensure_profile(session, user.id, user.email)
    changes = body.model_dump(exclude_unset=True)
    colors = changes.pop("palette_colors", None)
    if colors:
        changes |= {f"palette_{name}": value for name, value in colors.items()}
    if changes:
        session.execute(
            text(f"UPDATE app.users SET {set_clause(changes)} WHERE id = :id"),
            {**changes, "id": user.id},
        )
    return get_me(user, session)
