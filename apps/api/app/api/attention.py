"""What needs the business's attention today, for the dashboard: clients drifting away or whose
plan ends without a renewal, leads to call back, and health declarations waiting for review.
Each list appears only for people who may see it (and leads only with the CRM module)."""

import datetime as dt
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import TenantDep, has_module
from app.metrics import members_at_risk
from app.permissions import Permission

router = APIRouter(prefix="/attention", tags=["reports"])

RISK_DAYS = 14  # same window as the reports page's retention list
SHOWN = 5  # items per list; the count says how many there are in all


class AttentionItem(BaseModel):
    id: UUID
    name: str
    date: dt.date | None  # last visit, plan end, follow-up date or signing date


class AttentionList(BaseModel):
    kind: Literal["inactive", "plan_ending", "leads_due", "health_review"]
    count: int
    items: list[AttentionItem]


@router.get("")
def get_attention(context: TenantDep) -> list[AttentionList]:
    """Non-empty lists only, in the order the dashboard shows them."""
    db = context.session
    lists: list[AttentionList] = []

    if Permission.REPORTS_READ in context.permissions:
        risk = members_at_risk(db, RISK_DAYS, limit=500)
        for kind in ("plan_ending", "inactive"):
            members = [m for m in risk if m.reason == kind]
            items = [
                AttentionItem(
                    id=UUID(m.client_id),
                    name=m.name,
                    date=m.plan_ends_on if kind == "plan_ending" else m.last_visit,
                )
                for m in members[:SHOWN]
            ]
            lists.append(AttentionList(kind=kind, count=len(members), items=items))

    if Permission.CLIENTS_READ in context.permissions and has_module(db, "crm"):
        rows = (
            db.execute(
                text("""
                SELECT l.id, trim(l.first_name || ' ' || coalesce(l.last_name, '')) AS name,
                       l.follow_up_on AS date, count(*) OVER () AS total
                FROM app.leads l JOIN app.tenants t ON t.id = l.tenant_id
                WHERE l.stage NOT IN ('won', 'lost')
                  AND l.follow_up_on <= (now() AT TIME ZONE t.time_zone)::date
                ORDER BY l.follow_up_on, l.created_at
                LIMIT :shown
            """),
                {"shown": SHOWN},
            )
            .mappings()
            .all()
        )
        lists.append(_from_rows("leads_due", rows))

    if Permission.CLIENTS_READ in context.permissions:
        rows = (
            db.execute(
                text("""
                SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name,
                       (h.signed_at AT TIME ZONE t.time_zone)::date AS date,
                       count(*) OVER () AS total
                FROM app.health_declarations h
                JOIN app.clients c ON c.id = h.client_id
                JOIN app.tenants t ON t.id = h.tenant_id
                WHERE h.status = 'needs_review' AND c.erased_at IS NULL
                  AND NOT EXISTS (  -- only the client's latest declaration counts
                      SELECT 1 FROM app.health_declarations later
                      WHERE later.client_id = h.client_id AND later.signed_at > h.signed_at
                  )
                  AND (c.home_location_id IS NULL OR app.in_branch(c.home_location_id))
                ORDER BY h.signed_at
                LIMIT :shown
            """),
                {"shown": SHOWN},
            )
            .mappings()
            .all()
        )
        lists.append(_from_rows("health_review", rows))

    return [entry for entry in lists if entry.count > 0]


def _from_rows(kind: Literal["leads_due", "health_review"], rows: list) -> AttentionList:
    return AttentionList(
        kind=kind,
        count=rows[0]["total"] if rows else 0,
        items=[AttentionItem(id=r["id"], name=r["name"], date=r["date"]) for r in rows],
    )
