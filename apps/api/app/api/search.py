"""Global search (Cmd+K): one box that finds a client, lead, team member, class or invoice.

It is a thin layer over the lists the screens already have. Each kind is searched only if the
person holds the permission that opens its list, with the same branch rules (a member kept to some
branches never finds another branch's clients, classes or people), and every query runs inside the
tenant-scoped session, so row level security keeps it to one business. Few results per kind, and
the text is escaped, so a search is cheap and cannot be turned into a wildcard scan."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.clients import VISIBLE_CLIENTS
from app.api.deps import TenantContext, TenantDep, has_module
from app.core.permissions import Permission

router = APIRouter(prefix="/search", tags=["search"])

PER_KIND = 5
# The window of classes worth finding by name: from yesterday to a quarter ahead.
SESSIONS_BACK_DAYS = 1
SESSIONS_AHEAD_DAYS = 90

Kind = Literal["client", "lead", "staff", "session", "invoice"]


class SearchHit(BaseModel):
    kind: Kind
    id: UUID
    title: str
    subtitle: str | None = Field(
        default=None, description="Email, phone, branch or interest: what tells two hits apart"
    )
    tag: str | None = Field(
        default=None,
        description="Client status, lead stage, team role, or the kind of document",
    )
    at: datetime | None = Field(default=None, description="When a class starts")
    number: int | None = Field(default=None, description="An issued document's number")


class SearchResults(BaseModel):
    query: str
    items: list[SearchHit] = Field(description="At most five per kind, grouped by kind")


def _pattern(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _clients(context: TenantContext, pattern: str) -> list[SearchHit]:
    rows = context.session.execute(
        text(f"""
            SELECT id, trim(first_name || ' ' || coalesce(last_name, '')) AS title,
                   coalesce(email, phone) AS subtitle, status AS tag
            FROM app.clients
            {VISIBLE_CLIENTS}
              AND erased_at IS NULL
              AND id IN (SELECT app.search_client_ids(:pattern))
            ORDER BY first_name, last_name NULLS FIRST, id
            LIMIT :limit
        """),
        {"pattern": pattern, "limit": PER_KIND},
    ).mappings()
    return [SearchHit(kind="client", **row) for row in rows]


def _leads(context: TenantContext, pattern: str) -> list[SearchHit]:
    if not has_module(context.session, "crm"):
        return []
    rows = context.session.execute(
        text("""
            SELECT id, trim(first_name || ' ' || coalesce(last_name, '')) AS title,
                   coalesce(interest, email, phone) AS subtitle, stage AS tag
            FROM app.leads
            WHERE id IN (SELECT app.search_lead_ids(:pattern))
            ORDER BY stage_changed_at DESC, id
            LIMIT :limit
        """),
        {"pattern": pattern, "limit": PER_KIND},
    ).mappings()
    return [SearchHit(kind="lead", **row) for row in rows]


def _staff(context: TenantContext, pattern: str) -> list[SearchHit]:
    # A member kept to some branches finds themselves and the people at their branches only,
    # like the team page.
    narrowed = ""
    params: dict[str, object] = {"pattern": pattern, "limit": PER_KIND}
    if context.branches is not None:
        narrowed = """AND (m.user_id = app.current_user_id()
                           OR m.location_ids && CAST(:branches AS uuid[]))"""
        params["branches"] = [str(b) for b in context.branches]
    rows = context.session.execute(
        text(f"""
            SELECT m.user_id AS id, coalesce(nullif(u.full_name, ''), u.email) AS title,
                   coalesce(m.job_title, u.email) AS subtitle, m.role AS tag
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = app.current_tenant_id()
              AND (u.full_name ILIKE :pattern OR u.email ILIKE :pattern
                   OR m.job_title ILIKE :pattern)
              {narrowed}
            ORDER BY title, m.user_id
            LIMIT :limit
        """),
        params,
    ).mappings()
    return [SearchHit(kind="staff", **row) for row in rows]


def _sessions(context: TenantContext, pattern: str) -> list[SearchHit]:
    rows = context.session.execute(
        text("""
            SELECT s.id, sv.name AS title, l.name AS subtitle, s.starts_at AS at
            FROM app.sessions s
            JOIN app.services sv ON sv.id = s.service_id
            LEFT JOIN app.locations l ON l.id = s.location_id
            LEFT JOIN app.users u ON u.id = s.instructor_user_id
            WHERE sv.booking_mode = 'class' AND s.status = 'scheduled'
              AND s.starts_at >= now() - make_interval(days => :back)
              AND s.starts_at < now() + make_interval(days => :ahead)
              AND (s.location_id IS NULL OR app.in_branch(s.location_id))
              AND (sv.name ILIKE :pattern OR u.full_name ILIKE :pattern)
            ORDER BY s.starts_at, s.id
            LIMIT :limit
        """),
        {
            "pattern": pattern,
            "limit": PER_KIND,
            "back": SESSIONS_BACK_DAYS,
            "ahead": SESSIONS_AHEAD_DAYS,
        },
    ).mappings()
    return [SearchHit(kind="session", **row) for row in rows]


def _invoices(context: TenantContext, search: str, pattern: str) -> list[SearchHit]:
    # A document filed under a client follows that client's branch, so a member kept to some
    # branches never finds another branch's invoices.
    narrowed = ""
    params: dict[str, object] = {"pattern": pattern, "number": None, "limit": PER_KIND}
    if context.branches is not None:
        narrowed = (
            "AND (client_id IS NULL OR client_id IN "
            f"(SELECT id FROM app.clients {VISIBLE_CLIENTS}))"
        )
    if search.isascii() and search.isdigit() and len(search) <= 9:
        params["number"] = int(search)
    rows = context.session.execute(
        text(f"""
            SELECT id, client_name AS title, client_email AS subtitle, kind AS tag, number,
                   issued_at AS at
            FROM app.issued_documents
            WHERE (client_name ILIKE :pattern OR number = CAST(:number AS integer))
              {narrowed}
            ORDER BY issued_at DESC, id DESC
            LIMIT :limit
        """),
        params,
    ).mappings()
    return [SearchHit(kind="invoice", **row) for row in rows]


@router.get("")
def search(
    context: TenantDep,
    q: Annotated[str, Query(min_length=2, max_length=100, description="What to look for")],
) -> SearchResults:
    """Matches across the business, only in what the person may open: clients, leads and
    invoices need the same permissions as their lists, people need `staff.read`, classes
    `schedule.read`. Five hits per kind at most."""
    search_text = q.strip()
    if len(search_text) < 2:
        return SearchResults(query=search_text, items=[])
    pattern = _pattern(search_text)
    allowed = context.permissions
    items: list[SearchHit] = []
    if Permission.CLIENTS_READ in allowed:
        items += _clients(context, pattern)
        items += _leads(context, pattern)
    if Permission.STAFF_READ in allowed:
        items += _staff(context, pattern)
    if Permission.SCHEDULE_READ in allowed:
        items += _sessions(context, pattern)
    if Permission.SALES_MANAGE in allowed:
        items += _invoices(context, search_text, pattern)
    return SearchResults(query=search_text, items=items)
