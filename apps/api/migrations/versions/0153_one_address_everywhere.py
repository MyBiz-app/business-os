"""One address component everywhere (W2-5): city centers, and cities on leads, clients and the
business's own address.

Expand step only:

* `app.geo_cities.latitude/longitude/center_source`: a map point for each city, loaded from the
  file kept in the code (`app/geo/data/il_city_centers.json`), so the map no longer asks a free
  map service for city centers. `center_source` says whether the point is the city's own
  (`geonames`) or only the middle of its region (`region`).
* The structured address columns of 0129 (city, street, house number, details, unlisted street)
  on `app.tenants` (the legal address in settings) and `app.leads`, plus a composed text on leads.
  The older free-text columns of the business stay and are kept in step by the API.
* `app.clients.city_code`: the city a client comes from (import, CRM, the app's join step).
  Client street addresses stay in `app.client_addresses`.
* `app.set_my_city`: a client sets their own city; `app.submit_lead` also takes a city (a new
  overload, the old one stays for the previous release).

Existing rows keep their values and stay valid; the previous release never reads the new columns.

Revision ID: 0153
Revises: 0152
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

from app.geo.loader import load_centers

revision: str = "0153"
down_revision: str | None = "0152"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADDRESS_TABLES = ("tenants", "leads")
TENANT_ADDRESS = "city_code, street_code, house_number, address_details, street_unlisted"
OLD_SUBMIT = "app.submit_lead(text, text, text, text, text, text)"
NEW_SUBMIT = "app.submit_lead(text, text, text, text, text, text, integer)"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.geo_cities
            ADD COLUMN latitude      double precision CHECK (latitude BETWEEN -90 AND 90),
            ADD COLUMN longitude     double precision CHECK (longitude BETWEEN -180 AND 180),
            ADD COLUMN center_source text CHECK (center_source IN ('geonames', 'region')),
            ADD CONSTRAINT geo_cities_point_both CHECK ((latitude IS NULL) = (longitude IS NULL))
    """)
    load_centers(op.get_bind())

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
        op.execute(
            f"CREATE INDEX {table}_city_street_idx ON app.{table} (city_code, street_code) "
            "WHERE city_code IS NOT NULL"
        )
    op.execute(f"GRANT UPDATE ({TENANT_ADDRESS}) ON app.tenants TO app_api")
    op.execute("ALTER TABLE app.leads ADD COLUMN address text CHECK (char_length(address) <= 300)")

    op.execute(
        "ALTER TABLE app.clients ADD COLUMN city_code integer REFERENCES app.geo_cities (code)"
    )
    op.execute(
        "CREATE INDEX clients_city_idx ON app.clients (city_code, tenant_id) "
        "WHERE city_code IS NOT NULL"
    )
    op.execute("""
        CREATE FUNCTION app.set_my_city(p_city_code integer) RETURNS void
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            UPDATE app.clients SET city_code = p_city_code, updated_at = now()
            WHERE id = app.current_client_id() AND erased_at IS NULL
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.set_my_city(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.set_my_city(integer) TO app_api")

    op.execute("""
        CREATE FUNCTION app.submit_lead(
            p_code text, p_first_name text, p_last_name text, p_email text, p_phone text,
            p_interest text, p_city_code integer
        )
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid;
            v_id uuid;
        BEGIN
            SELECT t.id INTO v_tenant FROM app.tenants t
            WHERE t.join_code = upper(trim(p_code))
              AND EXISTS (SELECT 1 FROM app.tenant_modules m
                          WHERE m.tenant_id = t.id AND m.module_key = 'crm');
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no such form' USING ERRCODE = 'P0002';
            END IF;
            IF p_city_code IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM app.geo_cities c WHERE c.code = p_city_code) THEN
                RAISE EXCEPTION 'unknown city' USING ERRCODE = 'P0003';
            END IF;
            IF (SELECT count(*) FROM app.leads l
                WHERE l.tenant_id = v_tenant AND l.source = 'form'
                  AND l.created_at > now() - interval '1 hour'
                  AND (lower(l.email) = lower(p_email) OR l.phone = p_phone)) >= 3 THEN
                RAISE EXCEPTION 'too many requests' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.leads
                (tenant_id, first_name, last_name, email, phone, interest, source, city_code,
                 address)
            VALUES (v_tenant, p_first_name, p_last_name, lower(p_email), p_phone, p_interest,
                    'form', p_city_code,
                    (SELECT c.name_he FROM app.geo_cities c WHERE c.code = p_city_code))
            RETURNING id INTO v_id;
            INSERT INTO app.lead_activities (tenant_id, lead_id, kind, to_stage)
            VALUES (v_tenant, v_id, 'created', 'new');
            RETURN v_id;
        END
        $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {NEW_SUBMIT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {NEW_SUBMIT} TO app_api")


def downgrade() -> None:
    # contract: every function, column, index and constraint below was added by this same
    # migration; the previous release never reads them
    op.execute(f"DROP FUNCTION {NEW_SUBMIT}")
    op.execute("DROP FUNCTION app.set_my_city(integer)")
    op.execute("DROP INDEX app.clients_city_idx")
    op.execute("ALTER TABLE app.clients DROP COLUMN city_code")
    op.execute("ALTER TABLE app.leads DROP COLUMN address")
    op.execute(f"REVOKE UPDATE ({TENANT_ADDRESS}) ON app.tenants FROM app_api")
    for table in ADDRESS_TABLES:
        op.execute(f"""
            ALTER TABLE app.{table}
                DROP CONSTRAINT {table}_address_shape, DROP CONSTRAINT {table}_street_fk,
                DROP COLUMN street_unlisted, DROP COLUMN address_details,
                DROP COLUMN house_number, DROP COLUMN street_code, DROP COLUMN city_code
        """)
    op.execute("""
        ALTER TABLE app.geo_cities
            DROP COLUMN center_source, DROP COLUMN longitude, DROP COLUMN latitude
    """)
