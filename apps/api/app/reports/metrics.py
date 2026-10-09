"""The metrics layer: named, defined business metrics shared by dashboards and the AI.

Every number a screen or the AI shows comes from here, never from ad-hoc SQL, so they always
agree. A metric is computed for a period of local dates [start, end] in the business's time
zone. Queries run under the caller's tenant context (RLS applies)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

Unit = Literal["money", "count", "percent"]
Grain = Literal["day", "week", "month"]

# Local-date bounds of the period, as timestamptz, in the business's time zone.
PERIOD = """
    WITH tz AS (SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()),
    period AS (
        SELECT (CAST(:start AS date)::timestamp AT TIME ZONE tz.time_zone) AS from_at,
               ((CAST(:end AS date) + 1)::timestamp AT TIME ZONE tz.time_zone) AS to_at,
               tz.time_zone
        FROM tz
    )
"""

# Sessions that already happened (or are happening): the base of attendance metrics.
PAST_SESSIONS = """
    SELECT s.id, s.capacity FROM app.sessions s, period
    WHERE s.status = 'scheduled' AND s.starts_at >= period.from_at
      AND s.starts_at < least(period.to_at, now()) AND app.in_branch(s.location_id)
"""


@dataclass(frozen=True)
class Metric:
    key: str
    unit: Unit
    description: str  # for the AI's tool schema and docs (English, not shown to users)
    sql: str  # returns one value for :start..:end
    bucket_sql: str | None = None  # returns (bucket, value) per :grain, for charts
    higher_is_better: bool = True


def _bucketed(value_sql: str, timestamp: str) -> str:
    """Wraps per-row SQL so it groups by the local day/week/month of `timestamp`."""
    local = f"({timestamp}) AT TIME ZONE period.time_zone"
    return value_sql.replace("{bucket}", f"date_trunc(:grain, {local})::date")


REVENUE = Metric(
    key="revenue",
    unit="money",
    description="Money collected from plan sales (succeeded payments), in minor units.",
    sql=f"""{PERIOD}
        SELECT coalesce(sum(p.amount), 0) FROM app.payments p, period
        WHERE p.status = 'succeeded' AND p.created_at >= period.from_at
          AND p.created_at < period.to_at AND app.in_branch(p.location_id)
    """,
    bucket_sql=f"""{PERIOD}
        SELECT {{bucket}} AS bucket, sum(p.amount) AS value FROM app.payments p, period
        WHERE p.status = 'succeeded' AND p.created_at >= period.from_at
          AND p.created_at < period.to_at AND app.in_branch(p.location_id)
        GROUP BY 1 ORDER BY 1
    """,
)

PLANS_SOLD = Metric(
    key="plans_sold",
    unit="count",
    description="Number of memberships and punch cards sold.",
    sql=f"""{PERIOD}
        SELECT count(*) FROM app.entitlements e, period
        WHERE e.created_at >= period.from_at AND e.created_at < period.to_at
          AND app.in_branch(e.location_id)
    """,
)

ACTIVE_CLIENTS = Metric(
    key="active_clients",
    unit="count",
    description="Clients holding a valid (not cancelled) plan on the last day of the period.",
    sql="""
        SELECT count(DISTINCT e.client_id) FROM app.entitlements e
        WHERE e.status = 'active' AND CAST(:end AS date) BETWEEN e.starts_on AND e.ends_on
          AND app.in_branch(e.location_id)
    """,
)

NEW_CLIENTS = Metric(
    key="new_clients",
    unit="count",
    description="Clients added to the business during the period.",
    sql=f"""{PERIOD}
        SELECT count(*) FROM app.clients c, period
        WHERE c.created_at >= period.from_at AND c.created_at < period.to_at
          AND app.in_branch(c.home_location_id)
    """,
)

ATTENDANCE = Metric(
    key="attendance",
    unit="count",
    description="Check-ins: clients who came to a session in the period.",
    sql=f"""{PERIOD}
        SELECT count(*) FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id, period
        WHERE b.status = 'checked_in' AND s.starts_at >= period.from_at
          AND s.starts_at < period.to_at AND app.in_branch(s.location_id)
    """,
    bucket_sql=f"""{PERIOD}
        SELECT {{bucket}} AS bucket, count(*) AS value
        FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id, period
        WHERE b.status = 'checked_in' AND s.starts_at >= period.from_at
          AND s.starts_at < period.to_at AND app.in_branch(s.location_id)
        GROUP BY 1 ORDER BY 1
    """,
)

OCCUPANCY = Metric(
    key="occupancy",
    unit="percent",
    description="Share of spots taken in sessions that already took place (booked or attended "
    "or no-show, divided by capacity).",
    sql=f"""{PERIOD}, past AS ({PAST_SESSIONS})
        SELECT CASE WHEN sum(past.capacity) > 0 THEN
            100.0 * (SELECT count(*) FROM app.bookings b JOIN past ON past.id = b.session_id
                     WHERE b.status IN ('booked', 'checked_in', 'no_show'))
            / sum(past.capacity) END
        FROM past
    """,
)

NO_SHOW_RATE = Metric(
    key="no_show_rate",
    unit="percent",
    description="No-shows as a share of clients expected in sessions that took place.",
    sql=f"""{PERIOD}, past AS ({PAST_SESSIONS})
        SELECT CASE WHEN count(*) > 0 THEN
            100.0 * count(*) FILTER (WHERE b.status = 'no_show') / count(*) END
        FROM app.bookings b JOIN past ON past.id = b.session_id
        WHERE b.status IN ('checked_in', 'no_show')
    """,
    higher_is_better=False,
)

LATE_CANCEL_RATE = Metric(
    key="late_cancel_rate",
    unit="percent",
    description="Late cancellations as a share of all bookings for sessions in the period.",
    sql=f"""{PERIOD}
        SELECT CASE WHEN count(*) > 0 THEN
            100.0 * count(*) FILTER (WHERE b.late_cancel) / count(*) END
        FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id, period
        WHERE b.status <> 'waitlisted' AND s.starts_at >= period.from_at
          AND s.starts_at < period.to_at AND app.in_branch(s.location_id)
    """,
    higher_is_better=False,
)

SESSIONS_HELD = Metric(
    key="sessions_held",
    unit="count",
    description="Sessions that took place (not cancelled) in the period.",
    sql=f"{PERIOD} SELECT count(*) FROM ({PAST_SESSIONS}) past",
)

METRICS: dict[str, Metric] = {
    m.key: m
    for m in (
        REVENUE,
        ACTIVE_CLIENTS,
        NEW_CLIENTS,
        PLANS_SOLD,
        ATTENDANCE,
        OCCUPANCY,
        NO_SHOW_RATE,
        LATE_CANCEL_RATE,
        SESSIONS_HELD,
    )
}

MetricKey = Literal[
    "revenue",
    "active_clients",
    "new_clients",
    "plans_sold",
    "attendance",
    "occupancy",
    "no_show_rate",
    "late_cancel_rate",
    "sessions_held",
]


def compute(db: Session, key: str, start: date, end: date) -> float | None:
    value = db.execute(text(METRICS[key].sql), {"start": start, "end": end}).scalar()
    return None if value is None else round(float(value), 1)


def previous_period(start: date, end: date) -> tuple[date, date]:
    """The period of the same length right before [start, end]."""
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def series(db: Session, key: str, start: date, end: date, grain: Grain) -> list[tuple[date, float]]:
    """Values per day / week (starting Monday, ISO) / month; empty buckets are zero."""
    metric = METRICS[key]
    if metric.bucket_sql is None:
        raise ValueError(f"{key} has no series")
    sql = _bucketed(metric.bucket_sql, _TIMESTAMP[key])
    rows = dict(db.execute(text(sql), {"start": start, "end": end, "grain": grain}).all())
    return [(bucket, float(rows.get(bucket, 0))) for bucket in _buckets(start, end, grain)]


_TIMESTAMP: dict[str, str] = {"revenue": "p.created_at", "attendance": "s.starts_at"}


def _bucket_start(day: date, grain: Grain) -> date:
    if grain == "day":
        return day
    if grain == "week":
        return day - timedelta(days=day.weekday())  # Monday, as date_trunc('week')
    return day.replace(day=1)


def _buckets(start: date, end: date, grain: Grain) -> list[date]:
    buckets: list[date] = []
    day = _bucket_start(start, grain)
    while day <= end:
        buckets.append(day)
        if grain == "day":
            day += timedelta(days=1)
        elif grain == "week":
            day += timedelta(days=7)
        else:
            day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return buckets


# Breakdowns of the attendance metrics over sessions that took place, by one dimension. The
# definitions match OCCUPANCY and NO_SHOW_RATE above.
Dimension = Literal["service", "instructor", "time_slot", "branch"]

_DIMENSION_SQL: dict[str, tuple[str, str]] = {
    # (group key, label) expressions over s (sessions), sv (services), u (instructor user),
    # l (branch)
    "service": ("sv.id::text", "sv.name"),
    "branch": ("coalesce(l.id::text, '')", "coalesce(l.name, '')"),
    "instructor": ("coalesce(u.id::text, '')", "coalesce(u.full_name, u.email)"),
    # ISO weekday (1 = Monday) and local start hour, e.g. "1-18"; the client formats it.
    "time_slot": (
        "extract(isodow FROM s.starts_at AT TIME ZONE period.time_zone)::int || '-' || "
        "extract(hour FROM s.starts_at AT TIME ZONE period.time_zone)::int",
        "NULL",
    ),
}


@dataclass(frozen=True)
class BreakdownRow:
    key: str
    label: str | None
    sessions: int
    capacity: int
    taken: int  # booked, attended or no-show
    attended: int
    no_shows: int

    @property
    def occupancy(self) -> float | None:
        return 100.0 * self.taken / self.capacity if self.capacity else None

    @property
    def no_show_rate(self) -> float | None:
        expected = self.attended + self.no_shows
        return 100.0 * self.no_shows / expected if expected else None


def breakdown(db: Session, dimension: Dimension, start: date, end: date) -> list[BreakdownRow]:
    key_sql, label_sql = _DIMENSION_SQL[dimension]
    rows = db.execute(
        text(f"""{PERIOD}
            SELECT {key_sql} AS key, {label_sql} AS label, count(*) AS sessions,
                   sum(s.capacity) AS capacity, sum(bk.taken) AS taken,
                   sum(bk.attended) AS attended, sum(bk.no_shows) AS no_shows
            FROM app.sessions s
            JOIN app.services sv ON sv.id = s.service_id
            LEFT JOIN app.users u ON u.id = s.instructor_user_id
            LEFT JOIN app.locations l ON l.id = s.location_id
            CROSS JOIN period
            CROSS JOIN LATERAL (
                SELECT count(*) FILTER (WHERE b.status IN ('booked', 'checked_in', 'no_show'))
                           AS taken,
                       count(*) FILTER (WHERE b.status = 'checked_in') AS attended,
                       count(*) FILTER (WHERE b.status = 'no_show') AS no_shows
                FROM app.bookings b WHERE b.session_id = s.id
            ) bk
            WHERE s.status = 'scheduled' AND s.starts_at >= period.from_at
              AND s.starts_at < least(period.to_at, now()) AND app.in_branch(s.location_id)
            GROUP BY 1, 2
            ORDER BY sum(bk.attended) DESC, 2
        """),
        {"start": start, "end": end},
    ).all()
    return [
        BreakdownRow(
            key=row.key,
            label=row.label,
            sessions=row.sessions,
            capacity=int(row.capacity or 0),
            taken=int(row.taken or 0),
            attended=int(row.attended or 0),
            no_shows=int(row.no_shows or 0),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class MemberAtRisk:
    client_id: str
    name: str
    reason: Literal["inactive", "plan_ending"]
    last_visit: date | None  # local date
    plan_ends_on: date | None


def members_at_risk(db: Session, days: int, limit: int = 100) -> list[MemberAtRisk]:
    """Retention list: members with a valid plan and no check-in in `days` (inactive), and
    members whose last valid plan ends within `days` with nothing bought after it."""
    rows = db.execute(
        text("""
            WITH t AS (
                SELECT time_zone, (now() AT TIME ZONE time_zone)::date AS today
                FROM app.tenants WHERE id = app.current_tenant_id()
            ),
            members AS (
                SELECT c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name,
                       (SELECT max(e.ends_on) FROM app.entitlements e
                        WHERE e.client_id = c.id AND e.status = 'active'
                          AND e.ends_on >= t.today) AS plan_ends_on,
                       (SELECT max(s.starts_at) FROM app.bookings b
                        JOIN app.sessions s ON s.id = b.session_id
                        WHERE b.client_id = c.id AND b.status = 'checked_in') AS last_visit
                FROM app.clients c CROSS JOIN t
                WHERE c.erased_at IS NULL
                  -- clients without a home branch belong to every branch
                  AND (c.home_location_id IS NULL OR app.in_branch(c.home_location_id))
                  AND EXISTS (
                    SELECT 1 FROM app.entitlements e
                    WHERE e.client_id = c.id AND e.status = 'active'
                      AND t.today BETWEEN e.starts_on AND e.ends_on
                )
            )
            SELECT m.id::text AS client_id, m.name,
                   CASE WHEN m.last_visit IS NULL
                             OR m.last_visit < now() - make_interval(days => :days)
                        THEN 'inactive' ELSE 'plan_ending' END AS reason,
                   (m.last_visit AT TIME ZONE t.time_zone)::date AS last_visit,
                   m.plan_ends_on
            FROM members m CROSS JOIN t
            WHERE m.last_visit IS NULL OR m.last_visit < now() - make_interval(days => :days)
               OR m.plan_ends_on < t.today + :days
            ORDER BY reason, m.last_visit NULLS FIRST, m.plan_ends_on
            LIMIT :limit
        """),
        {"days": days, "limit": limit},
    ).mappings()
    return [MemberAtRisk(**row) for row in rows]
