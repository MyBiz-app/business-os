"""Gives demo clients, leads and people a home city and street from the official lists.

    place_residents(conn, tenant_ids)

Each person lives near one of their business's branches: most in the branch's own city, some in
the cities around it, a few far away (so the map shows an honest spread, with single clients in
faraway towns). Which city a person gets depends only on their id, so a rerun gives the same
answer and only fills what is still empty. Cities come with their stored centers, streets from
the street list; nothing calls an outside service."""

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Connection, text

# Share of people in the branch's city, the near ring, the far ring and the rest of the country.
RING_WEIGHTS = (0.55, 0.30, 0.11, 0.04)
NEAR_KM = (0.1, 30.0)
FAR_KM = (30.0, 90.0)
RING_SIZE = 8
MIN_STREETS = 20  # a city with fewer streets is a village: people live there, but are rare
FAR_COUNT = 6
FALLBACK_CITIES = ("תל אביב - יפו", "רמת גן", "חיפה", "ירושלים", "באר שבע", "פתח תקווה")


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    chord = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(chord))


class Residents:
    """Picks a home for a person, given the city of the branch they are around."""

    def __init__(self, conn: Connection) -> None:
        rows = conn.execute(
            text("""
                SELECT c.code, c.name_he, c.latitude, c.longitude,
                       (SELECT count(*) FROM app.geo_streets s
                         WHERE s.city_code = c.code) AS streets
                FROM app.geo_cities c ORDER BY c.code
            """)
        ).all()
        self.conn = conn
        self.names = {r.code: r.name_he for r in rows}
        self.points = {r.code: (r.latitude, r.longitude) for r in rows if r.latitude is not None}
        self.towns = [r.code for r in rows if r.streets >= MIN_STREETS and r.code in self.points]
        biggest = sorted((r for r in rows if r.code in self.points), key=lambda r: -r.streets)
        self.far = [r.code for r in biggest[: FAR_COUNT * 4]]
        self.fallback = [c for c, n in self.names.items() if n in FALLBACK_CITIES]
        self._rings: dict[int, tuple[list[int], list[int]]] = {}
        self._streets: dict[int, list[tuple[int, str]]] = {}

    def rings(self, base: int) -> tuple[list[int], list[int]]:
        if base not in self._rings:
            origin = self.points.get(base)
            near: list[tuple[float, int]] = []
            far: list[tuple[float, int]] = []
            for code in self.towns:
                if origin is None or code == base:
                    continue
                distance = _km(origin, self.points[code])
                if NEAR_KM[0] <= distance < NEAR_KM[1]:
                    near.append((distance, code))
                elif FAR_KM[0] <= distance < FAR_KM[1] or NEAR_KM[1] <= distance < FAR_KM[0]:
                    far.append((distance, code))
            near.sort()
            far.sort()
            self._rings[base] = (
                [c for _, c in near[:RING_SIZE]],
                [c for _, c in far[:RING_SIZE]],
            )
        return self._rings[base]

    def city_for(self, key: str, base: int | None) -> int:
        rng = random.Random(f"city:{key}")
        if base is None or base not in self.names:
            return rng.choice(self.fallback or self.towns)
        near, far = self.rings(base)
        pools = [[base], near or [base], far or near or [base], self.far]
        ring = rng.choices(range(4), weights=RING_WEIGHTS)[0]
        return rng.choice(pools[ring])

    def street_for(self, key: str, city: int) -> tuple[int, str] | None:
        if city not in self._streets:
            self._streets[city] = [
                (r.code, r.name_he)
                for r in self.conn.execute(
                    text(
                        "SELECT code, name_he FROM app.geo_streets WHERE city_code = :c "
                        "ORDER BY code"
                    ),
                    {"c": city},
                )
            ]
        streets = self._streets[city]
        return random.Random(f"street:{key}").choice(streets) if streets else None

    def home(self, key: str, base: int | None, city: int | None = None) -> dict[str, Any]:
        """city_code, street_code, house_number and the text lines for a person; `city` fixes
        the city (a person who is also a client lives where their client record says)."""
        city = city or self.city_for(key, base)
        street = self.street_for(key, city)
        house = str(random.Random(f"house:{key}").randint(1, 80)) if street else None
        line = f"{street[1]} {house}" if street else None
        return {
            "city_code": city,
            "street_code": street[0] if street else None,
            "street_name": street[1] if street else None,
            "house_number": house,
            "line": line,
            "city_name": self.names[city],
            "address": ", ".join(p for p in (line, self.names[city]) if p),
        }


def place_residents(conn: Connection, tenant_ids: Sequence[Any]) -> dict[str, int]:
    """Fills the city of demo clients and leads (and their street address) and of demo people
    that have none yet, around the branches of the given businesses."""
    residents = Residents(conn)
    branches: dict[Any, list[int | None]] = defaultdict(list)
    branch_city: dict[Any, int | None] = {}
    for row in conn.execute(
        text(
            "SELECT id, tenant_id, city_code FROM app.locations WHERE tenant_id = ANY(:t) "
            "ORDER BY created_at, id"
        ),
        {"t": list(tenant_ids)},
    ):
        branches[row.tenant_id].append(row.city_code)
        branch_city[row.id] = row.city_code

    def tenant_base(tenant: Any, key: str) -> int | None:
        cities = [c for c in branches.get(tenant, []) if c is not None]
        return random.Random(f"base:{key}").choice(cities) if cities else None

    counts = {"clients": 0, "addresses": 0, "leads": 0, "people": 0}

    clients = conn.execute(
        text("""
            SELECT c.id, c.tenant_id, c.home_location_id, c.user_id,
                   EXISTS (SELECT 1 FROM app.client_addresses a
                           WHERE a.client_id = c.id AND a.active) AS has_address
            FROM app.clients c
            WHERE c.tenant_id = ANY(:t) AND c.city_code IS NULL AND c.erased_at IS NULL
        """),
        {"t": list(tenant_ids)},
    ).all()
    for client in clients:
        key = str(client.user_id or client.id)  # one person, one home in every business
        base = branch_city.get(client.home_location_id) or tenant_base(client.tenant_id, key)
        home = residents.home(key, base)
        conn.execute(
            text("UPDATE app.clients SET city_code = :city WHERE id = :id"),
            {"city": home["city_code"], "id": client.id},
        )
        counts["clients"] += 1
        if home["street_code"] is not None and not client.has_address:
            conn.execute(
                text("""
                    INSERT INTO app.client_addresses
                        (tenant_id, client_id, label, street, city, city_code, street_code,
                         house_number)
                    VALUES (:tenant, :client, 'בית', :line, :city, :city_code, :street_code,
                            :house)
                """),
                {
                    "tenant": client.tenant_id,
                    "client": client.id,
                    "line": home["line"],
                    "city": home["city_name"],
                    "city_code": home["city_code"],
                    "street_code": home["street_code"],
                    "house": home["house_number"],
                },
            )
            counts["addresses"] += 1

    leads = conn.execute(
        text("SELECT id, tenant_id FROM app.leads WHERE tenant_id = ANY(:t) AND city_code IS NULL"),
        {"t": list(tenant_ids)},
    ).all()
    for lead in leads:
        key = f"lead:{lead.id}"
        home = residents.home(key, tenant_base(lead.tenant_id, key))
        conn.execute(
            text("""
                UPDATE app.leads SET city_code = :city_code, street_code = :street_code,
                       house_number = :house_number, address = :address WHERE id = :id
            """),
            {**home, "id": lead.id},
        )
        counts["leads"] += 1

    people = conn.execute(
        text("""
            SELECT u.id,
                   (SELECT c.city_code FROM app.clients c
                    WHERE c.user_id = u.id AND c.city_code IS NOT NULL LIMIT 1) AS client_city,
                   (SELECT m.tenant_id FROM app.tenant_members m
                    WHERE m.user_id = u.id AND m.tenant_id = ANY(:t) LIMIT 1) AS member_of
            FROM app.users u
            WHERE u.email LIKE 'demo-%@example.invalid' AND u.city_code IS NULL
              AND (EXISTS (SELECT 1 FROM app.tenant_members m
                           WHERE m.user_id = u.id AND m.tenant_id = ANY(:t))
                   OR EXISTS (SELECT 1 FROM app.clients c
                              WHERE c.user_id = u.id AND c.tenant_id = ANY(:t)))
        """),
        {"t": list(tenant_ids)},
    ).all()
    for person in people:
        key = str(person.id)
        home = residents.home(key, tenant_base(person.member_of, key), person.client_city)
        conn.execute(
            text("""
                UPDATE app.users SET city_code = :city_code, street_code = :street_code,
                       house_number = :house_number, address_line = :line, city = :city_name
                WHERE id = :id
            """),
            {**home, "id": person.id},
        )
        counts["people"] += 1
    return counts
