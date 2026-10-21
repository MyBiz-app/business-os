"""Where a business's clients live, by city: the numbers behind the "planned branch" game.

Inside one business nothing is hidden: every client counts, also a single one from a far city
(the business already sees its clients' addresses). Each client counts once, in the city on their
record or else the city of their latest saved address. A city's point comes from the city list,
so no client address is sent anywhere; cities without a known centre are counted but cannot be
placed on the map."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CityClients:
    city_code: int
    city_name: str
    clients: int
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class ClientCities:
    clients_total: int
    clients_without_city: int
    cities: list[CityClients]


def client_cities(db: Session) -> ClientCities:
    """The business's clients (leads and erased people left out) by the city of their latest
    saved address, most first."""
    total = db.execute(
        text("SELECT count(*) FROM app.clients WHERE status <> 'lead' AND erased_at IS NULL")
    ).scalar_one()
    rows = db.execute(
        text("""
            SELECT g.code AS city_code, g.name_he AS city_name, g.latitude, g.longitude,
                   count(*) AS clients
            FROM app.clients c
            CROSS JOIN LATERAL (
                SELECT coalesce(c.city_code, (
                    SELECT a.city_code FROM app.client_addresses a
                    WHERE a.client_id = c.id AND a.active AND a.city_code IS NOT NULL
                    ORDER BY a.updated_at DESC LIMIT 1
                )) AS city_code
            ) addr
            JOIN app.geo_cities g ON g.code = addr.city_code
            WHERE c.status <> 'lead' AND c.erased_at IS NULL
            GROUP BY g.code, g.name_he, g.latitude, g.longitude
            ORDER BY count(*) DESC, g.name_he
        """)
    ).all()
    cities = [
        CityClients(row.city_code, row.city_name, row.clients, row.latitude, row.longitude)
        for row in rows
    ]
    return ClientCities(
        clients_total=total,
        clients_without_city=total - sum(c.clients for c in cities),
        cities=cities,
    )
