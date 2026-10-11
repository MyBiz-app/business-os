"""The person's businesses at a glance ("My businesses"): every business they belong to, with its
industry, branches and the key numbers of today and this month. Each business is read under its
own tenant context, so RLS keeps their data apart even here; money is only shown where the
person's role in that business may read reports."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep
from app.api.routes import ensure_profile
from app.api.schemas import Role
from app.core.db import set_tenant
from app.core.permissions import effective_permissions
from app.reports.metrics import compute

router = APIRouter(tags=["account"])


class BusinessSummary(BaseModel):
    tenant_id: UUID
    name: str
    vertical: str
    role: Role
    logo_url: str | None
    primary_color: str | None
    currency: str
    branches: list[str] = Field(description="Names of the active branches")
    sessions_today: int
    active_clients: int | None = Field(description="Null when the role may not read reports")
    revenue_month: int | None = Field(description="Minor units; null without reports.read")


@router.get("/me/businesses")
def list_my_businesses(user: UserDep, session: SessionDep) -> list[BusinessSummary]:
    ensure_profile(session, user.id, user.email)
    memberships = session.execute(
        text("""
            SELECT m.tenant_id, m.role, r.permissions AS custom_permissions
            FROM app.tenant_members m
            JOIN app.tenants t ON t.id = m.tenant_id
            LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
            WHERE m.user_id = app.current_user_id()
            ORDER BY t.created_at
        """)
    ).all()
    summaries = []
    for membership in memberships:
        set_tenant(session, membership.tenant_id)
        row = (
            session.execute(
                text("""
                    SELECT t.id AS tenant_id, t.name, t.vertical, t.primary_color,
                           CASE WHEN t.logo IS NULL THEN NULL
                                ELSE '/public/tenants/' || t.id || '/logo?v='
                                     || extract(epoch FROM t.logo_updated_at)::bigint
                           END AS logo_url,
                           t.currency, (now() AT TIME ZONE t.time_zone)::date AS today,
                           coalesce((SELECT array_agg(l.name ORDER BY l.created_at)
                                     FROM app.locations l WHERE l.active), '{}') AS branches,
                           (SELECT count(*) FROM app.sessions s
                            WHERE s.status = 'scheduled'
                              AND (s.starts_at AT TIME ZONE t.time_zone)::date
                                  = (now() AT TIME ZONE t.time_zone)::date) AS sessions_today
                    FROM app.tenants t WHERE t.id = app.current_tenant_id()
                """)
            )
            .mappings()
            .one()
        )
        today: date = row["today"]
        reports = "reports.read" in effective_permissions(
            membership.role, membership.custom_permissions
        )
        active = compute(session, "active_clients", today, today) if reports else None
        revenue = compute(session, "revenue", today.replace(day=1), today) if reports else None
        summaries.append(
            BusinessSummary(
                **{k: v for k, v in row.items() if k != "today"},
                role=membership.role,
                active_clients=None if active is None else int(active),
                revenue_month=None if revenue is None else int(revenue),
            )
        )
    return summaries
