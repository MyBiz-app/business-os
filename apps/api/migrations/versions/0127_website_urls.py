"""A website address for the business and for each branch (round 7, R22).

Expand step: `app.tenants.website_url` and `app.locations.website_url` (both optional; a branch
without its own address uses the business's). The public join-code lookup also returns the
business's address, so the join page can link to it. Existing rows stay empty and the previous
release keeps working: it never selects the new columns, and the lookup keeps every column it
returned before.

Revision ID: 0127
Revises: 0126
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0127"
down_revision: str | None = "0126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("tenants", "locations"):
        op.execute(f"""
            ALTER TABLE app.{table}
                ADD COLUMN website_url text
                    CONSTRAINT {table}_website_url_check
                    CHECK (website_url ~ '^https?://[^[:space:]]+$' AND length(website_url) <= 300)
        """)
    op.execute("GRANT UPDATE (website_url) ON app.tenants TO app_api")
    # The lookup gains one trailing column; a function's result type cannot change in place.
    op.execute("DROP FUNCTION app.business_by_join_code(text)")
    op.execute("""
        CREATE FUNCTION app.business_by_join_code(p_code text)
        RETURNS TABLE (id uuid, name text, locale text, primary_color text,
                       logo_updated_at timestamptz, client_app boolean, website_url text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id, t.name, t.locale, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END,
                   EXISTS (SELECT 1 FROM app.tenant_modules m
                           WHERE m.tenant_id = t.id AND m.module_key = 'client_app'),
                   t.website_url
            FROM app.tenants t WHERE t.join_code = upper(trim(p_code))
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.business_by_join_code(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.business_by_join_code(text) TO app_api")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (website_url) ON app.tenants FROM app_api")
    op.execute("DROP FUNCTION app.business_by_join_code(text)")
    op.execute("""
        CREATE FUNCTION app.business_by_join_code(p_code text)
        RETURNS TABLE (id uuid, name text, locale text, primary_color text,
                       logo_updated_at timestamptz, client_app boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id, t.name, t.locale, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END,
                   EXISTS (SELECT 1 FROM app.tenant_modules m
                           WHERE m.tenant_id = t.id AND m.module_key = 'client_app')
            FROM app.tenants t WHERE t.join_code = upper(trim(p_code))
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.business_by_join_code(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.business_by_join_code(text) TO app_api")
    # contract: the columns were added by this same migration; the previous release never reads them
    op.execute("ALTER TABLE app.locations DROP COLUMN website_url")
    op.execute("ALTER TABLE app.tenants DROP COLUMN website_url")
