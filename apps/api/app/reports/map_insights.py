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


# What leaves the business for the AI: a count under this is never shown (the cross-business rule).
AI_MIN_COUNT = 5
AI_MAX_AREAS = 15


def branch_city_codes(db: Session) -> set[int]:
    rows = db.execute(
        text("SELECT DISTINCT city_code FROM app.locations WHERE city_code IS NOT NULL")
    ).all()
    return {row.city_code for row in rows}


def areas_for_ai(db: Session, start: dt.date, end: dt.date) -> dict:
    """The map as the AI may see it: counts only, no names of people, no addresses, no ids. A
    count under AI_MIN_COUNT is left out, and a city where both counts are small is not listed;
    the small cities are only added up when together they reach the minimum."""
    found = map_insights(db, start, end)
    branches = branch_city_codes(db)
    shown: list[dict] = []
    rest_clients = rest_leads = 0
    for area in found.areas:
        clients = area.clients if area.clients >= AI_MIN_COUNT else None
        leads = area.leads if area.leads >= AI_MIN_COUNT else None
        if clients is None and leads is None:
            rest_clients += area.clients
            rest_leads += area.leads
            continue
        row: dict = {
            "city": area.city_name,
            "has_branch_in_city": area.city_code in branches,
            "clients": clients,
            "new_clients": area.new_clients if clients is not None else None,
            "leads": leads,
            "leads_won": area.leads_won if leads is not None else None,
            "lead_conversion_percent": (
                round(100 * area.leads_won / area.leads) if leads is not None else None
            ),
        }
        shown.append(row)
    # Only the biggest cities go to the model; what is cut joins the "other" totals.
    for row in shown[AI_MAX_AREAS:]:
        rest_clients += row["clients"] or 0
        rest_leads += row["leads"] or 0
    shown = shown[:AI_MAX_AREAS]
    return {
        "areas": shown,
        "other_cities": {
            "clients": rest_clients if rest_clients >= AI_MIN_COUNT else None,
            "leads": rest_leads if rest_leads >= AI_MIN_COUNT else None,
        },
        "clients_total": found.clients_total,
        "leads_total": found.leads_total,
        "note": (
            f"Counts under {AI_MIN_COUNT} are hidden (null). Leads are those that arrived in the "
            "period; clients are everyone now. Suggest, never act."
        ),
    }
