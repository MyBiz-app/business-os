from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, TenantDep, UserDep
from app.api.schemas import Me, Membership, Tenant, TenantCreate
from app.core.db import set_tenant
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
                       t.primary_color, t.cancellation_window_minutes, m.role,
                       CASE WHEN t.logo IS NULL THEN NULL
                            ELSE '/public/tenants/' || t.id || '/logo?v='
                                 || extract(epoch FROM t.logo_updated_at)::bigint END AS logo_url
                FROM app.tenants t
                JOIN app.tenant_members m
                    ON m.tenant_id = t.id AND m.user_id = app.current_user_id()
                WHERE t.id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    return Tenant.model_validate(dict(row))


@router.get("/me", tags=["account"])
def get_me(user: UserDep, session: SessionDep) -> Me:
    ensure_profile(session, user.id, user.email)
    profile = (
        session.execute(
            text("SELECT id, email, full_name, locale FROM app.users WHERE id = :id"),
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
    tenant_id: UUID = session.execute(
        text("SELECT app.create_tenant(:name, :vertical, :locale, :time_zone, :currency)"),
        body.model_dump(),
    ).scalar_one()
    set_tenant(session, tenant_id)
    pack = VERTICAL_PACKS[body.vertical]
    session.execute(
        text("UPDATE app.tenants SET cancellation_window_minutes = :minutes WHERE id = :id"),
        {"minutes": pack.cancellation_window_minutes, "id": tenant_id},
    )
    return load_current_tenant(session)


@router.get("/tenants/current", tags=["tenants"])
def get_current_tenant(context: TenantDep) -> Tenant:
    return load_current_tenant(context.session)
