"""A business can choose to appear in the join screen's search (app upgrade, slice U6).

A person without a join code can look a business up by name in the app. Nothing is listed unless
the owner turns it on: `tenants.listed_in_search` defaults to off. The search function returns
only the join code, the name, the logo and the city of listed businesses, and needs at least
two characters, so it cannot be used to browse the whole directory.

Revision ID: 0161
Revises: 0160
Create Date: 2026-10-25
"""

# contract: only the downgrade drops what this migration added; the upgrade just adds a column
# and a function.

from collections.abc import Sequence

from alembic import op

revision: str = "0161"
down_revision: str | None = "0160"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN listed_in_search boolean NOT NULL DEFAULT false")
    op.execute("GRANT UPDATE (listed_in_search) ON app.tenants TO app_api")
    op.execute(r"""
        CREATE FUNCTION app.search_listed_businesses(p_query text)
        RETURNS TABLE (join_code text, name text, city text, primary_color text,
                       logo_updated_at timestamptz, id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.join_code, t.name, t.address_city, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END, t.id
            FROM app.tenants t
            WHERE t.listed_in_search
              AND length(trim(p_query)) >= 2
              AND t.name ILIKE '%' || replace(replace(replace(trim(p_query), '\', '\\'),
                                                      '%', '\%'), '_', '\_') || '%'
              AND EXISTS (SELECT 1 FROM app.tenant_modules m
                          WHERE m.tenant_id = t.id AND m.module_key = 'client_app')
            ORDER BY t.name
            LIMIT 10
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.search_listed_businesses(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.search_listed_businesses(text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.search_listed_businesses(text)")
    op.execute("REVOKE UPDATE (listed_in_search) ON app.tenants FROM app_api")
    op.execute("ALTER TABLE app.tenants DROP COLUMN listed_in_search")
