"""The business's insights map: where clients and leads are, city by city.

Inside one business nothing is hidden (the same rule as client_cities.py): every client and lead
counts, also a single one from a far city, and there is no minimum. Only counts leave this
module, never a name or an address; city points come from our own city list, so nothing is sent
to an outside geocoder. The k >= 5 threshold belongs to the cross-business console and the AI,
not here."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

# Israel has about 1,300 listed cities; the cap only keeps the answer bounded.
MAX_AREAS = 2000


@dataclass(frozen=True)
class Area:
    city_code: int
    city_name: str
    latitude: float | None
    longitude: float | None
    clients: int
    new_clients: int
    leads: int
    leads_won: int


@dataclass(frozen=True)
class MapInsights:
    clients_total: int
    clients_without_city: int
    leads_total: int
    leads_without_city: int
    areas: list[Area]


def map_insights(db: Session, start: dt.date, end: dt.date) -> MapInsights:
    """Clients (leads and erased people left out) and leads by city. `clients` is everyone now;
    `new_clients` joined, and `leads` arrived, in [start, end] (business time zone); `leads_won`
    is the part of those leads that were won."""
    rows = db.execute(
        text("""
            WITH tz AS (SELECT coalesce(t.time_zone, 'UTC') AS time_zone FROM app.tenants t
                        WHERE t.id = app.current_tenant_id()),
            win AS (
                SELECT (CAST(:start AS date)::timestamp AT TIME ZONE tz.time_zone) AS a,
                       ((CAST(:end AS date) + 1)::timestamp AT TIME ZONE tz.time_zone) AS b
                FROM tz
            ),
            people AS (
                SELECT addr.city_code, 1 AS clients,
                       CASE WHEN c.created_at >= win.a AND c.created_at < win.b
                            THEN 1 ELSE 0 END AS new_clients, 0 AS leads, 0 AS leads_won
                FROM app.clients c CROSS JOIN win
                CROSS JOIN LATERAL (
                    SELECT coalesce(c.city_code, (
                        SELECT a.city_code FROM app.client_addresses a
                        WHERE a.client_id = c.id AND a.active AND a.city_code IS NOT NULL
                        ORDER BY a.updated_at DESC LIMIT 1
                    )) AS city_code
                ) addr
                WHERE c.status <> 'lead' AND c.erased_at IS NULL
                UNION ALL
                SELECT l.city_code, 0, 0, 1, CASE WHEN l.stage = 'won' THEN 1 ELSE 0 END
                FROM app.leads l CROSS JOIN win
                WHERE l.created_at >= win.a AND l.created_at < win.b
            )
            SELECT g.code AS city_code, g.name_he AS city_name, g.latitude, g.longitude,
                   sum(p.clients) AS clients, sum(p.new_clients) AS new_clients,
                   sum(p.leads) AS leads, sum(p.leads_won) AS leads_won
            FROM people p
            JOIN app.geo_cities g ON g.code = p.city_code
            GROUP BY g.code, g.name_he, g.latitude, g.longitude
            ORDER BY sum(p.clients) + sum(p.leads) DESC, g.name_he
            LIMIT :limit
        """),
        {"start": start, "end": end, "limit": MAX_AREAS},
    ).all()
    areas = [
        Area(
            row.city_code,
            row.city_name,
            row.latitude,
            row.longitude,
            int(row.clients),
            int(row.new_clients),
            int(row.leads),
            int(row.leads_won),
        )
        for row in rows
    ]
    totals = db.execute(
        text("""
            SELECT
              (SELECT count(*) FROM app.clients WHERE status <> 'lead' AND erased_at IS NULL)
                AS clients,
              (SELECT count(*) FROM app.leads l
               WHERE l.created_at >= (CAST(:start AS date)::timestamp AT TIME ZONE
                       (SELECT coalesce(time_zone, 'UTC') FROM app.tenants
                        WHERE id = app.current_tenant_id()))
                 AND l.created_at < ((CAST(:end AS date) + 1)::timestamp AT TIME ZONE
                       (SELECT coalesce(time_zone, 'UTC') FROM app.tenants
                        WHERE id = app.current_tenant_id()))) AS leads
        """),
        {"start": start, "end": end},
    ).one()
    return MapInsights(
        clients_total=totals.clients,
        clients_without_city=totals.clients - sum(a.clients for a in areas),
        leads_total=totals.leads,
        leads_without_city=totals.leads - sum(a.leads for a in areas),
        areas=areas,
    )
