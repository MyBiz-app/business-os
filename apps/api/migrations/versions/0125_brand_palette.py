"""The default palette is called `brand`, not the product's name (round 7, R21).

Expand step: `app.users.palette` accepts `brand` next to `mybiz`. The API writes `brand` and reads
a stored `mybiz` as `brand`, so no row is rewritten here and the previous release keeps working
on this database. A later release rewrites the old rows and drops `mybiz` from the check.

Revision ID: 0125
Revises: 0124
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0125"
down_revision: str | None = "0124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.users DROP CONSTRAINT IF EXISTS users_palette_check")
    op.execute("""
        ALTER TABLE app.users
            ADD CONSTRAINT users_palette_check
                CHECK (palette IN ('brand', 'mybiz', 'ocean', 'forest', 'custom'))
    """)


def downgrade() -> None:
    op.execute("UPDATE app.users SET palette = 'mybiz' WHERE palette = 'brand'")
    op.execute("ALTER TABLE app.users DROP CONSTRAINT IF EXISTS users_palette_check")
    op.execute("""
        ALTER TABLE app.users
            ADD CONSTRAINT users_palette_check
                CHECK (palette IN ('mybiz', 'ocean', 'forest', 'custom'))
    """)
