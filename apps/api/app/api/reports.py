"""Business KPIs from the metrics layer (app/metrics.py)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import TenantContext, require
from app.metrics import METRICS, Grain, MetricKey, Unit, compute, previous_period, series
from app.permissions import Permission

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
