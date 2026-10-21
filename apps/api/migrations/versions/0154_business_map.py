"""The MyBiz console's map of businesses and where their clients live (CRM Premium W2-4).

One read-only function, no table changes. It counts, per city of the official list:

* `businesses`: the businesses with an active branch in the city, and
* `clients`: the clients (leads and erased people left out) whose city is there (the city on
  their record, else the city of their latest saved address),

each split by the business's industry. Only totals leave the database, never a name: a city with
fewer than `p_min` (and never fewer than 5) is left out whole, and an industry with fewer than
that in a city shows up as "mixed" (a NULL industry), so one business or one person cannot be
picked out. The floor is enforced here, not only in the API.

Revision ID: 0154
Revises: 0153
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0154"
down_revision: str | None = "0153"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.platform_business_map(p_min integer)
        RETURNS TABLE (layer text, city_code integer, city_name text, latitude double precision,
                       longitude double precision, vertical text, total bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            floor_n integer := greatest(coalesce(p_min, 5), 5);
        BEGIN
            IF NOT app.platform_can('businesses.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            WITH cells AS (
                SELECT 'businesses'::text AS layer, s.city_code, s.vertical, count(*) AS n
                FROM (
                    SELECT DISTINCT l.tenant_id, l.city_code, t.vertical
                    FROM app.locations l
                    JOIN app.tenants t ON t.id = l.tenant_id AND t.closed_at IS NULL
                    WHERE l.active AND l.city_code IS NOT NULL
                ) s
                GROUP BY s.city_code, s.vertical
                UNION ALL
                SELECT 'clients', h.city_code, h.vertical, count(*)
                FROM (
                    SELECT addr.city_code, t.vertical
                    FROM app.clients c
                    JOIN app.tenants t ON t.id = c.tenant_id AND t.closed_at IS NULL
                    CROSS JOIN LATERAL (
                        SELECT coalesce(c.city_code, (
                            SELECT a.city_code FROM app.client_addresses a
                            WHERE a.client_id = c.id AND a.tenant_id = c.tenant_id AND a.active
                              AND a.city_code IS NOT NULL
                            ORDER BY a.updated_at DESC LIMIT 1
                        )) AS city_code
                    ) addr
                    WHERE addr.city_code IS NOT NULL
                      AND c.status <> 'lead' AND c.erased_at IS NULL
                ) h
                GROUP BY h.city_code, h.vertical
            ),
            kept AS (
                SELECT x.layer, x.city_code FROM cells x
                GROUP BY x.layer, x.city_code HAVING sum(x.n) >= floor_n
            )
            SELECT c.layer, c.city_code, g.name_he, g.latitude, g.longitude,
                   CASE WHEN c.n >= floor_n THEN c.vertical END,
                   sum(c.n)::bigint
            FROM cells c
            JOIN kept k ON k.layer = c.layer AND k.city_code = c.city_code
            JOIN app.geo_cities g ON g.code = c.city_code
            GROUP BY c.layer, c.city_code, g.name_he, g.latitude, g.longitude,
                     CASE WHEN c.n >= floor_n THEN c.vertical END
            ORDER BY c.layer, g.name_he, 6;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_business_map(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_business_map(integer) TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops the function, and the previous release never calls it.
    op.execute("DROP FUNCTION app.platform_business_map(integer)")
