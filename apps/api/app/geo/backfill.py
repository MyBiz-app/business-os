"""Gives every branch that has an address but no map point its city, street and point.

Branches made before the map existed (the demo ones) only carry the address as text. This reads
that text ("Herzl 120, Tel Aviv"), finds the city and street in the official lists and looks the
point up once. A street the map service does not know falls back to the city's centre, so the
branch still lands in the right place. Safe to run again: it only touches branches without a point.

    uv run python -m app.seed --owner-email you@example.com --demo places
"""

import logging
import re
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.geo.addresses import resolve_address, search_cities, search_streets
from app.geo.geocoder import Geocoder, get_geocoder
from app.geo.snapshot import normalize_search

log = logging.getLogger(__name__)

_DETAILS = re.compile(r"\s*\([^)]*\)\s*$")
_STREET_AND_HOUSE = re.compile(r"^(?P<street>.+?)\s+(?P<house>\d+[\w\-/]*)$")


def split_address(address: str) -> tuple[str | None, str | None, str]:
    """ "Herzl 120, Tel Aviv (floor 2)" -> ("Herzl", "120", "Tel Aviv"). A text without a comma is
    taken as a city alone."""
    line = _DETAILS.sub("", address).strip()
    street_part, comma, city = line.rpartition(",")
    if not comma:
        return None, None, line
    street_part = street_part.strip()
    parts = _STREET_AND_HOUSE.match(street_part)
    if parts:
        return parts["street"].strip(), parts["house"], city.strip()
    return street_part or None, None, city.strip()


def _best(found: list[dict[str, Any]], wanted: str) -> dict[str, Any] | None:
    """The exact name when the list has it, else the first (best) hit."""
    target = normalize_search(wanted)
    for row in found:
        if normalize_search(row["name_he"]) == target:
            return row
    return found[0] if found else None


def locate_branches(
    conn: Connection, geocoder: Geocoder | None = None, pause: float = 0.0
) -> dict[str, int]:
    """Locates every branch without a point. `pause` (seconds) spaces the map service requests;
    its usage policy asks for at most one a second."""
    geocoder = geocoder or get_geocoder()
    rows = conn.execute(
        text("""
            SELECT id, address FROM app.locations
            WHERE latitude IS NULL AND longitude IS NULL
              AND address IS NOT NULL AND btrim(address) <> ''
            ORDER BY created_at, id
        """)
    ).all()
    done = {"located": 0, "city_only": 0, "unplaced": 0}
    with Session(bind=conn, autoflush=False) as lists:
        for location_id, address in rows:
            street_name, house, city_name = split_address(address)
            city = _best(search_cities(lists, city_name, 5), city_name)
            if city is None:
                log.warning("branch %s: city %r is not on the list", location_id, city_name)
                done["unplaced"] += 1
                continue
            street = (
                _best(search_streets(lists, city["code"], street_name, 5), street_name)
                if street_name
                else None
            )
            fields: dict[str, Any] = {
                "city_code": city["code"],
                "street_code": street["code"] if street else None,
                "street_unlisted": None if street else street_name,
                "house_number": house if street_name else None,
            }
            try:
                resolved = resolve_address(lists, fields, required=False)
            except HTTPException:
                done["unplaced"] += 1
                continue
            point = geocoder.find(street=resolved.street, house_number=house, city=city["name_he"])
            exact = point is not None
            if point is None and resolved.street:
                if pause:
                    time.sleep(pause)
                point = geocoder.find(street=None, house_number=None, city=city["name_he"])
            if pause:
                time.sleep(pause)
            conn.execute(
                text("""
                    UPDATE app.locations SET
                        city_code = :city_code, street_code = :street_code,
                        house_number = :house_number, street_unlisted = :street_unlisted,
                        latitude = :latitude, longitude = :longitude,
                        geocoded_at = CASE WHEN CAST(:latitude AS float8) IS NULL
                                           THEN NULL ELSE now() END
                    WHERE id = :id
                """),
                {
                    **resolved.columns,
                    "latitude": point.latitude if point else None,
                    "longitude": point.longitude if point else None,
                    "id": location_id,
                },
            )
            done["located" if exact else "city_only" if point else "unplaced"] += 1
    return done
