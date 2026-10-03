"""Business branding: primary color and logo.

The logo is stored in Postgres for the prototype (small images only, served by the API).
It moves to object storage (Supabase Storage) when images grow beyond logos.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN primary_color text CHECK (primary_color ~ '^#[0-9a-fA-F]{6}$'),
            ADD COLUMN logo bytea CHECK (octet_length(logo) <= 524288),
            ADD COLUMN logo_content_type text
                CHECK (logo_content_type IN ('image/png', 'image/jpeg', 'image/webp')),
            ADD COLUMN logo_updated_at timestamptz
    """)
    # Logos are public (clients see them before signing in); only the image is exposed.
    op.execute("""
        CREATE FUNCTION app.tenant_logo(p_tenant_id uuid)
        RETURNS TABLE (logo bytea, content_type text, updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.logo, t.logo_content_type, t.logo_updated_at
            FROM app.tenants t WHERE t.id = p_tenant_id AND t.logo IS NOT NULL
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.tenant_logo(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.tenant_logo(uuid) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.tenant_logo(uuid)")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN primary_color, DROP COLUMN logo, DROP COLUMN logo_content_type,
            DROP COLUMN logo_updated_at
    """)
