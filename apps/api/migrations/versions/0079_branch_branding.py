"""Branch branding: a logo and an accent color per branch.

A branch can carry its own logo and primary color. A branch that sets none shows the network's
(the business's own logo and color): the API resolves that fallback, the columns stay empty.
The logo is kept in the database like the business logo, and served publicly by branch id.

Revision ID: 0079
Revises: 0078
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0079"
down_revision: str | None = "0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.locations
            ADD COLUMN primary_color text CHECK (primary_color ~ '^#[0-9a-fA-F]{6}$'),
            ADD COLUMN logo bytea CHECK (octet_length(logo) <= 524288),
            ADD COLUMN logo_content_type text
                CHECK (logo_content_type IN ('image/png', 'image/jpeg', 'image/webp')),
            ADD COLUMN logo_updated_at timestamptz
    """)
    op.execute("""
        CREATE FUNCTION app.location_logo(p_location_id uuid)
        RETURNS TABLE (logo bytea, content_type text, updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT l.logo, l.logo_content_type, l.logo_updated_at
            FROM app.locations l WHERE l.id = p_location_id AND l.logo IS NOT NULL
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.location_logo(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.location_logo(uuid) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.location_logo(uuid)")
    op.execute("""
        ALTER TABLE app.locations
            DROP COLUMN primary_color, DROP COLUMN logo, DROP COLUMN logo_content_type,
            DROP COLUMN logo_updated_at
    """)
