"""The business's audit log, for its owner and unrestricted managers (go-live, GL7).

Who changed a role, invited or removed someone, exported payroll, signed in from a new device,
and so on. Newest first, paged by keyset (the position of the last row seen) so a long log stays
cheap; filters by person, kind and date; the same view as CSV. Entries are kept 24 months."""

import csv
import datetime as dt
import io
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import TenantContext, require
from app.core.audit import record
from app.core.permissions import Permission

router = APIRouter(prefix="/audit-log", tags=["settings"])

CATEGORIES = (
    "team",
    "settings",
    "security",
    "payroll",
    "privacy",
    "export",
    "support",
    "other",
)
PAGE_SIZE = 50
EXPORT_LIMIT = 10_000


def require_audit_reader(
    context: Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))],
) -> TenantContext:
    """Owners and managers of the whole business; not people kept to some branches."""
    if context.branches is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return context


AuditDep = Annotated[TenantContext, Depends(require_audit_reader)]


class AuditLogEntry(BaseModel):
    id: int
    occurred_at: dt.datetime
    actor_type: str
    actor_id: UUID | None
    actor_name: str | None
    actor_email: str | None
    action: str
    category: str
    entity_type: str | None
    entity_id: UUID | None
    details: dict[str, Any]


class AuditLogPage(BaseModel):
    entries: list[AuditLogEntry]
    next_cursor: str | None = Field(description="Pass as `cursor` for the next (older) page")


class AuditFilters(BaseModel):
    actor_id: UUID | None = None
    category: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None


def _filters(
    actor_id: Annotated[UUID | None, Query(description="Only this person's actions")] = None,
    category: Annotated[
        str | None, Query(description="One of the kinds, see /audit-log/kinds")
    ] = None,
    date_from: Annotated[dt.date | None, Query(description="From this day (business time)")] = None,
    date_to: Annotated[dt.date | None, Query(description="Up to and including this day")] = None,
) -> AuditFilters:
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="unknown_category")
    return AuditFilters(actor_id=actor_id, category=category, date_from=date_from, date_to=date_to)


FiltersDep = Annotated[AuditFilters, Depends(_filters)]

SELECT = """
    SELECT a.id, a.occurred_at, a.actor_type, a.actor_id,
           coalesce(u.full_name, a.details->>'name') AS actor_name,
           coalesce(u.email, a.details->>'email') AS actor_email,
           a.action, a.category, a.entity_type, a.entity_id, a.details
    FROM app.audit_log a
    LEFT JOIN app.users u ON u.id = a.actor_id
    WHERE (CAST(:actor_id AS uuid) IS NULL OR a.actor_id = :actor_id)
      AND (CAST(:category AS text) IS NULL OR a.category = :category)
      AND (CAST(:date_from AS date) IS NULL OR a.occurred_at >=
           CAST(:date_from AS date)::timestamp AT TIME ZONE
           (SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()))
      AND (CAST(:date_to AS date) IS NULL OR a.occurred_at <
           (CAST(:date_to AS date) + 1)::timestamp AT TIME ZONE
           (SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()))
"""

ORDER_LIMIT = " ORDER BY a.occurred_at DESC, a.id DESC LIMIT :limit"


def _params(filters: AuditFilters) -> dict[str, Any]:
    return filters.model_dump()


def _encode(entry: AuditLogEntry) -> str:
    return f"{entry.occurred_at.isoformat()}|{entry.id}"


def _decode(cursor: str) -> tuple[dt.datetime, int]:
    try:
        when, entry_id = cursor.rsplit("|", 1)
        return dt.datetime.fromisoformat(when), int(entry_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid_cursor") from error


@router.get("")
def list_audit_log(
    context: AuditDep,
    filters: FiltersDep,
    cursor: Annotated[str | None, Query(description="From a previous page")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = PAGE_SIZE,
) -> AuditLogPage:
    params = _params(filters) | {"limit": limit + 1, "after_at": None, "after_id": None}
    keyset = ""
    if cursor:
        params["after_at"], params["after_id"] = _decode(cursor)
        keyset = " AND (a.occurred_at, a.id) < (:after_at, :after_id)"
    rows = (
        context.session.execute(
            text(SELECT + keyset + ORDER_LIMIT), params
        )
        .mappings()
        .all()
    )
    entries = [AuditLogEntry.model_validate(dict(row)) for row in rows[:limit]]
    return AuditLogPage(
        entries=entries, next_cursor=_encode(entries[-1]) if len(rows) > limit else None
    )


@router.get("/kinds")
def list_kinds(context: AuditDep) -> list[str]:
    return list(CATEGORIES)


def _safe(value: str) -> str:
    """A spreadsheet runs a cell that starts with = + - @ as a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@router.get("/export")
def export_audit_log(context: AuditDep, filters: FiltersDep) -> Response:
    """The filtered log as CSV (the latest 10,000 entries). The export is itself logged."""
    rows = (
        context.session.execute(
            text(SELECT + ORDER_LIMIT),
            _params(filters) | {"limit": EXPORT_LIMIT},
        )
        .mappings()
        .all()
    )
    record(
        context.session,
        "export.audit_log",
        entity_type="tenant",
        entity_id=context.tenant_id,
        rows=len(rows),
        category=filters.category,
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["time_utc", "person", "email", "kind", "action", "entity", "details"])
    for row in rows:
        writer.writerow(
            [
                row["occurred_at"].astimezone(dt.UTC).isoformat(timespec="seconds"),
                _safe(row["actor_name"] or ""),
                _safe(row["actor_email"] or ""),
                row["category"],
                row["action"],
                f"{row['entity_type'] or ''} {row['entity_id'] or ''}".strip(),
                _safe(json.dumps(row["details"], ensure_ascii=False, sort_keys=True)),
            ]
        )
    return Response(
        content="﻿" + out.getvalue(),  # Excel opens Hebrew right with a BOM
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
