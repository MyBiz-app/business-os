"""Industries come from the shared catalog (packages/verticals), so the database no longer
keeps its own list: a contact request's industry is checked by the API against the catalog,
like a business's industry already is.

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.contact_requests DROP CONSTRAINT contact_requests_vertical_check")
    op.execute("""
        ALTER TABLE app.contact_requests ADD CONSTRAINT contact_requests_vertical_check
            CHECK (vertical ~ '^[a-z][a-z0-9_]{0,39}$')
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app.contact_requests DROP CONSTRAINT contact_requests_vertical_check")
    op.execute("""
        UPDATE app.contact_requests SET vertical = 'other'
        WHERE vertical NOT IN ('fitness', 'beauty', 'clinic', 'garage', 'other')
    """)
    op.execute("""
        ALTER TABLE app.contact_requests ADD CONSTRAINT contact_requests_vertical_check
            CHECK (vertical IN ('fitness', 'beauty', 'clinic', 'garage', 'other'))
    """)
