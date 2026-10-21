"""Loads the snapshot into the shared city and street tables (insert new, update changed).

Rows are never deleted: addresses already saved point at them. Used by the migration that
creates the tables and by `python -m app.geo.loader` after a yearly refresh of the snapshot."""

import json
from pathlib import Path

from sqlalchemy import Connection, text

from app.geo.snapshot import cities, read_snapshot, streets

CENTERS = Path(__file__).parent / "data" / "il_city_centers.json"


def load_snapshot(connection: Connection) -> tuple[int, int]:
    """Returns how many cities and streets the snapshot holds."""
    data = read_snapshot()
    raw = connection.connection  # the DBAPI connection: COPY is far faster than 60k INSERTs
    with raw.cursor() as cursor:
        cursor.execute(
            "CREATE TEMP TABLE geo_cities_in (LIKE app.geo_cities INCLUDING DEFAULTS) "
            "ON COMMIT DROP"
        )
        cursor.execute(
            "CREATE TEMP TABLE geo_streets_in (LIKE app.geo_streets INCLUDING DEFAULTS) "
            "ON COMMIT DROP"
        )
        with cursor.copy(
            "COPY geo_cities_in (code, name_he, name_en, region_code, region_name, search_text) "
            "FROM STDIN"
        ) as copy:
            for city in cities(data):
                copy.write_row(
                    (
                        city.code,
                        city.name_he,
                        city.name_en,
                        city.region_code,
                        city.region_name,
                        city.search_text,
                    )
                )
        with cursor.copy(
            "COPY geo_streets_in (city_code, code, name_he, aliases, search_text) FROM STDIN"
        ) as copy:
            for street in streets(data):
                copy.write_row(
                    (
                        street.city_code,
                        street.code,
                        street.name_he,
                        street.aliases,
                        street.search_text,
                    )
                )
        cursor.execute("""
            INSERT INTO app.geo_cities
                (code, name_he, name_en, region_code, region_name, search_text)
            SELECT code, name_he, name_en, region_code, region_name, search_text
            FROM geo_cities_in
            ON CONFLICT (code) DO UPDATE SET
                name_he = EXCLUDED.name_he, name_en = EXCLUDED.name_en,
                region_code = EXCLUDED.region_code, region_name = EXCLUDED.region_name,
                search_text = EXCLUDED.search_text
        """)
        cursor.execute("""
            INSERT INTO app.geo_streets (city_code, code, name_he, aliases, search_text)
            SELECT city_code, code, name_he, aliases, search_text FROM geo_streets_in
            ON CONFLICT (city_code, code) DO UPDATE SET
                name_he = EXCLUDED.name_he, aliases = EXCLUDED.aliases,
                search_text = EXCLUDED.search_text
        """)
    return len(data["cities"]), sum(len(rows) for rows in data["streets"].values())


def load_centers(connection: Connection) -> int:
    """Sets the map point of each city from the centers file (scripts/build_geo_centers.py).
    Returns how many cities got a point."""
    centers = json.loads(CENTERS.read_text(encoding="utf-8"))
    connection.execute(
        text("""
            UPDATE app.geo_cities c
            SET latitude = v.latitude, longitude = v.longitude, center_source = v.source
            FROM (SELECT (r->>0)::int AS code, (r->>1)::float8 AS latitude,
                         (r->>2)::float8 AS longitude, r->>3 AS source
                  FROM jsonb_array_elements(CAST(:rows AS jsonb)) r) v
            WHERE c.code = v.code
        """),
        {"rows": json.dumps([[int(code), *row] for code, row in centers.items()])},
    )
    return len(centers)


if __name__ == "__main__":  # pragma: no cover - run by hand after refreshing the snapshot
    from sqlalchemy import create_engine

    from app.core.config import get_settings

    with create_engine(get_settings().database_url).begin() as conn:
        print("loaded cities and streets:", load_snapshot(conn))
        print("city centers:", load_centers(conn))
