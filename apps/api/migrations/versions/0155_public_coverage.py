"""The landing page's "MyBiz across the country" map (CRM Premium W5-4).

One read-only function, no table changes, callable without signing in. It counts, per city of
the official list, the open businesses with an active branch there. Nothing else leaves the
database: no business name, no industry, no client, no address. A city with fewer than five
businesses is left out whole (the floor is enforced here, so the API cannot ask for less), so a
single business can never be picked out.

Revision ID: 0155
Revises: 0154
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0155"
down_revision: str | None = "0154"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.public_coverage()
        RETURNS TABLE (city_code integer, city_name text, city_name_en text,
                       latitude double precision, longitude double precision, businesses bigint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT g.code, g.name_he, g.name_en, g.latitude, g.longitude, count(*)::bigint
            FROM (
                SELECT DISTINCT l.tenant_id, l.city_code
                FROM app.locations l
                JOIN app.tenants t ON t.id = l.tenant_id AND t.closed_at IS NULL
                WHERE l.active AND l.city_code IS NOT NULL
            ) s
            JOIN app.geo_cities g ON g.code = s.city_code
            WHERE g.latitude IS NOT NULL AND g.longitude IS NOT NULL
            GROUP BY g.code, g.name_he, g.name_en, g.latitude, g.longitude
            HAVING count(*) >= 5
            ORDER BY count(*) DESC, g.name_he
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.public_coverage() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.public_coverage() TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops the function, and the previous release never calls it.
    op.execute("DROP FUNCTION app.public_coverage()")
