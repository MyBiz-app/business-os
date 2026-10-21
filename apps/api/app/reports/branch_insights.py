"""Extra numbers for the branches map: where a branch's clients live, and what its team costs.

No new tables: client origins come from the clients' saved addresses, staff cost from the latest
payroll run split by where each person clocked in."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

TOP_CITIES = 6
# A city is shown only when at least this many clients come from it, so no single client can be
# picked out of the map (privacy, R35).
MIN_CLIENTS_PER_CITY = 5


@dataclass(frozen=True)
class Origin:
    city_code: int
    city_name: str
    clients: int
    latitude: float | None
    longitude: float | None


def client_origins(db: Session, location_id: str, start: dt.date, end: dt.date) -> list[Origin]:
    """The cities of the clients who booked a session at the branch in [start, end], most first.
    A client counts once, in the city on their record, else the city of their latest saved
    address. City centers come from the city list. Cities with fewer than MIN_CLIENTS_PER_CITY
    clients are left out."""
    rows = db.execute(
        text("""
            WITH tz AS (SELECT coalesce(t.time_zone, 'UTC') AS time_zone FROM app.tenants t
                        WHERE t.id = app.current_tenant_id()),
            visitors AS (
                SELECT DISTINCT b.client_id
                FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id, tz
                WHERE s.location_id = CAST(:location AS uuid) AND app.in_branch(s.location_id)
                  AND b.status IN ('booked', 'checked_in', 'no_show')
                  AND s.starts_at >= (CAST(:start AS date)::timestamp AT TIME ZONE tz.time_zone)
                  AND s.starts_at < ((CAST(:end AS date) + 1)::timestamp AT TIME ZONE tz.time_zone)
            )
            SELECT c.code AS city_code, c.name_he AS city_name, c.latitude, c.longitude,
                   count(*) AS clients
            FROM visitors v
            JOIN app.clients cl ON cl.id = v.client_id
            CROSS JOIN LATERAL (
                SELECT coalesce(cl.city_code, (
                    SELECT a.city_code FROM app.client_addresses a
                    WHERE a.client_id = v.client_id AND a.active AND a.city_code IS NOT NULL
                    ORDER BY a.updated_at DESC LIMIT 1
                )) AS city_code
            ) addr
            JOIN app.geo_cities c ON c.code = addr.city_code
            GROUP BY c.code, c.name_he, c.latitude, c.longitude
            HAVING count(*) >= :min_clients
            ORDER BY count(*) DESC, c.name_he
            LIMIT :limit
        """),
        {
            "location": location_id,
            "start": start,
            "end": end,
            "limit": TOP_CITIES,
            "min_clients": MIN_CLIENTS_PER_CITY,
        },
    ).all()
    return [
        Origin(row.city_code, row.city_name, row.clients, row.latitude, row.longitude)
        for row in rows
    ]


def staff_cost_by_branch(db: Session) -> tuple[dt.date | None, dict[str, int]]:
    """The latest payroll month's gross pay per branch, in minor units. Each person's gross is
    split by their clocked minutes in that month (people who did not clock in are left out)."""
    run = db.execute(
        text("""
            SELECT id, period FROM app.payroll_runs
            ORDER BY (stage = 'approved') DESC, period DESC LIMIT 1
        """)
    ).first()
    if run is None:
        return None, {}
    rows = db.execute(
        text("""
            WITH tz AS (SELECT coalesce(t.time_zone, 'UTC') AS time_zone FROM app.tenants t
                        WHERE t.id = app.current_tenant_id()),
            minutes AS (
                SELECT e.user_id, e.location_id,
                       sum(extract(epoch FROM e.clock_out - e.clock_in)) AS seconds
                FROM app.time_clock_entries e, tz
                WHERE e.clock_out IS NOT NULL
                  AND e.clock_in >= (CAST(:period AS date)::timestamp AT TIME ZONE tz.time_zone)
                  AND e.clock_in < ((CAST(:period AS date) + interval '1 month')::timestamp
                                    AT TIME ZONE tz.time_zone)
                GROUP BY 1, 2
            ),
            totals AS (SELECT user_id, sum(seconds) AS seconds FROM minutes GROUP BY 1)
            SELECT m.location_id::text AS location_id,
                   round(sum(l.gross_minor * m.seconds / nullif(t.seconds, 0)))::bigint AS cost
            FROM app.payroll_run_lines l
            JOIN minutes m ON m.user_id = l.user_id
            JOIN totals t ON t.user_id = m.user_id
            WHERE l.run_id = :run AND app.in_branch(m.location_id)
            GROUP BY 1
        """),
        {"run": run.id, "period": run.period},
    ).all()
    return run.period, {row.location_id: int(row.cost or 0) for row in rows}


def staff_count_by_branch(db: Session) -> dict[str, int]:
    """Team members tied to each branch: assigned to it, or with it as their home branch."""
    rows = db.execute(
        text("""
            SELECT l.id::text AS location_id, count(m.user_id) AS members
            FROM app.locations l
            JOIN app.tenant_members m
              ON m.home_location_id = l.id OR l.id = ANY(m.location_ids)
            WHERE l.active AND app.in_branch(l.id)
            GROUP BY l.id
        """)
    ).all()
    return {row.location_id: int(row.members) for row in rows}
