"""Israeli cities and streets, structured addresses and branch coordinates (round 7, R34).

Expand step only:

* `app.geo_cities` and `app.geo_streets`: the official lists from data.gov.il, shared by every
  business and read-only for the API (the same pattern as `vat_rates`). Loaded from the snapshot
  kept in the code (`app/geo/data`), never deleted from afterwards: saved addresses point at them.
  A trigram index answers "street names containing these letters" inside one city.
* A structured address (city, street, house number, details) next to the existing free text on
  `app.locations`, `app.users` (the personal profile) and `app.client_addresses`. A street that
  is missing from the list is typed into `street_unlisted` and stays visible for review.
* `app.locations.latitude/longitude/geocoded_at`: the branch's point on the map.

Existing rows keep their text and stay valid; the previous release never reads the new columns.

Revision ID: 0129
Revises: 0127
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

from app.geo.loader import load_snapshot

revision: str = "0129"
down_revision: str | None = "0127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADDRESS_TABLES = ("locations", "users", "client_addresses")


def _into_extensions(extension: str) -> str:
    return f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = '{extension}') THEN
                ALTER EXTENSION {extension} SET SCHEMA extensions;
            ELSE
                CREATE EXTENSION {extension} WITH SCHEMA extensions;
            END IF;
        END $$
    """


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute(_into_extensions("pg_trgm"))
    op.execute("""
        CREATE TABLE app.geo_cities (
            code        integer PRIMARY KEY,
            name_he     text NOT NULL CHECK (length(trim(name_he)) > 0),
            name_en     text,
            region_code integer,
            region_name text,
            search_text text NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE app.geo_streets (
            city_code   integer NOT NULL REFERENCES app.geo_cities (code),
            code        integer NOT NULL,
            name_he     text NOT NULL CHECK (length(trim(name_he)) > 0),
            aliases     text[] NOT NULL DEFAULT '{}',
            search_text text NOT NULL,
            PRIMARY KEY (city_code, code)
        )
    """)
    op.execute(
        "CREATE INDEX geo_streets_search_trgm_idx ON app.geo_streets "
        "USING gin (search_text extensions.gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX geo_cities_name_trgm_idx ON app.geo_cities "
        "USING gin (search_text extensions.gin_trgm_ops)"
    )
    for table in ("geo_cities", "geo_streets"):
        op.execute(f"GRANT SELECT ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_read ON app.{table} FOR SELECT TO app_api USING (true)")
    load_snapshot(op.get_bind())

    for table in ADDRESS_TABLES:
        op.execute(f"""
            ALTER TABLE app.{table}
                ADD COLUMN city_code      integer REFERENCES app.geo_cities (code),
                ADD COLUMN street_code    integer,
                ADD COLUMN house_number   text CHECK (char_length(house_number) <= 20),
                ADD COLUMN address_details text CHECK (char_length(address_details) <= 100),
                ADD COLUMN street_unlisted text CHECK (char_length(street_unlisted) <= 120),
                ADD CONSTRAINT {table}_street_fk FOREIGN KEY (city_code, street_code)
                    REFERENCES app.geo_streets (city_code, code),
                ADD CONSTRAINT {table}_address_shape CHECK (
                    (street_code IS NULL OR city_code IS NOT NULL)
                    AND (street_unlisted IS NULL OR street_code IS NULL))
        """)
        # Deleting a city or street row (a yearly refresh) checks these keys.
        op.execute(
            f"CREATE INDEX {table}_city_street_idx ON app.{table} (city_code, street_code) "
            "WHERE city_code IS NOT NULL"
        )
    op.execute("""
        ALTER TABLE app.locations
            ADD COLUMN latitude double precision CHECK (latitude BETWEEN -90 AND 90),
            ADD COLUMN longitude double precision CHECK (longitude BETWEEN -180 AND 180),
            ADD COLUMN geocoded_at timestamptz,
            ADD CONSTRAINT locations_point_both CHECK ((latitude IS NULL) = (longitude IS NULL))
    """)


def downgrade() -> None:
    # contract: every column and table below was added by this same migration; the previous
    # release never reads them
    op.execute("""
        ALTER TABLE app.locations
            DROP COLUMN geocoded_at, DROP COLUMN longitude, DROP COLUMN latitude
    """)
    for table in ADDRESS_TABLES:
        op.execute(f"""
            ALTER TABLE app.{table}
                DROP CONSTRAINT {table}_address_shape, DROP CONSTRAINT {table}_street_fk,
                DROP COLUMN street_unlisted, DROP COLUMN address_details,
                DROP COLUMN house_number, DROP COLUMN street_code, DROP COLUMN city_code
        """)
    op.execute("DROP TABLE app.geo_streets")
    op.execute("DROP TABLE app.geo_cities")
