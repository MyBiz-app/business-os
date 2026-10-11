"""Business KPIs from the metrics layer (app/reports/metrics.py)."""

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import TenantContext, require
from app.core.permissions import Permission
from app.reports.metrics import (
    METRICS,
    Dimension,
    Grain,
    MetricKey,
    Unit,
    breakdown,
    compute,
    members_at_risk,
    previous_period,
    series,
)

router = APIRouter(prefix="/metrics", tags=["reports"])

ReportsDep = Annotated[TenantContext, Depends(require(Permission.REPORTS_READ))]

MAX_DAYS = 366


class MetricValue(BaseModel):
    key: MetricKey
    unit: Unit
    value: float | None
    previous: float | None
    higher_is_better: bool


class Point(BaseModel):
    bucket: dt.date
    value: float


def _check_period(start: dt.date, end: dt.date) -> None:
    if end < start or (end - start).days >= MAX_DAYS:
        raise HTTPException(status_code=422, detail="invalid_period")


@router.get("")
def get_metrics(
    context: ReportsDep,
    start: Annotated[dt.date, Query(description="First local date")],
    end: Annotated[dt.date, Query(description="Last local date (inclusive)")],
    keys: Annotated[list[MetricKey] | None, Query()] = None,
) -> list[MetricValue]:
    """Each metric for the period and for the period of the same length just before it."""
    _check_period(start, end)
    before_start, before_end = previous_period(start, end)
    return [
        MetricValue(
            key=key,
            unit=METRICS[key].unit,
            value=compute(context.session, key, start, end),
            previous=compute(context.session, key, before_start, before_end),
            higher_is_better=METRICS[key].higher_is_better,
        )
        for key in keys or list(METRICS)
    ]


@router.get("/{key}/series")
def get_series(
    key: MetricKey,
    context: ReportsDep,
    start: Annotated[dt.date, Query()],
    end: Annotated[dt.date, Query()],
    grain: Annotated[Grain, Query()] = "week",
) -> list[Point]:
    _check_period(start, end)
    if METRICS[key].bucket_sql is None:
        raise HTTPException(status_code=422, detail="no_series")
    return [
        Point(bucket=bucket, value=value)
        for bucket, value in series(context.session, key, start, end, grain)
    ]


class BreakdownItem(BaseModel):
    key: str = Field(description="Service id, instructor user id ('' = none) or 'isodow-hour'")
    label: str | None
    sessions: int
    attended: int
    occupancy: float | None = Field(description="Percent of capacity taken")
    no_show_rate: float | None = Field(description="Percent of expected clients who didn't come")


@router.get("/breakdown/{dimension}")
def get_breakdown(
    dimension: Dimension,
    context: ReportsDep,
    start: Annotated[dt.date, Query()],
    end: Annotated[dt.date, Query()],
) -> list[BreakdownItem]:
    """Attendance metrics of sessions that took place, per service, instructor or time slot."""
    _check_period(start, end)
    return [
        BreakdownItem(
            key=row.key,
            label=row.label,
            sessions=row.sessions,
            attended=row.attended,
            occupancy=row.occupancy,
            no_show_rate=row.no_show_rate,
        )
        for row in breakdown(context.session, dimension, start, end)
    ]


class MemberAtRisk(BaseModel):
    client_id: str
    name: str
    reason: Literal["inactive", "plan_ending"]
    last_visit: dt.date | None
    plan_ends_on: dt.date | None


@router.get("/members-at-risk")
def get_members_at_risk(
    context: ReportsDep, days: Annotated[int, Query(ge=7, le=180)] = 14
) -> list[MemberAtRisk]:
    """Members with a valid plan who haven't come in `days`, or whose plan ends within `days`
    with no renewal."""
    return [
        MemberAtRisk.model_validate(member.__dict__)
        for member in members_at_risk(context.session, days)
    ]


class BranchMetric(BaseModel):
    key: MetricKey
    unit: Unit
    value: float | None
    higher_is_better: bool


class BranchMetrics(BaseModel):
    location_id: str
    name: str
    metrics: list[BranchMetric]


@router.get("/branches")
def compare_branches(
    context: ReportsDep,
    start: Annotated[dt.date, Query(description="First local date")],
    end: Annotated[dt.date, Query(description="Last local date (inclusive)")],
    keys: Annotated[list[MetricKey] | None, Query()] = None,
    location_id: Annotated[
        list[str] | None, Query(description="Only these branches (within the person's own)")
    ] = None,
) -> list[BranchMetrics]:
    """The same metrics, branch by branch, for comparing them side by side. Each value uses
    the metric's single definition with that one branch selected, so the numbers add up to
    the business's own. Only branches the person may see are compared."""
    _check_period(start, end)
    db = context.session
    branches = db.execute(
        text("""
            SELECT id::text AS id, name FROM app.locations
            WHERE active AND app.in_branch(id) ORDER BY created_at, name
        """)
    ).all()
    if location_id:
        wanted = set(location_id)
        branches = [b for b in branches if b.id in wanted]
    previous = db.execute(text("SELECT current_setting('app.location_id', true)")).scalar()
    result = []
    try:
        for branch in branches:
            db.execute(text("SELECT set_config('app.location_id', :id, true)"), {"id": branch.id})
            result.append(
                BranchMetrics(
                    location_id=branch.id,
                    name=branch.name,
                    metrics=[
                        BranchMetric(
                            key=key,
                            unit=METRICS[key].unit,
                            value=compute(db, key, start, end),
                            higher_is_better=METRICS[key].higher_is_better,
                        )
                        for key in keys or list(METRICS)
                    ],
                )
            )
    finally:
        db.execute(text("SELECT set_config('app.location_id', :id, true)"), {"id": previous or ""})
    return result
