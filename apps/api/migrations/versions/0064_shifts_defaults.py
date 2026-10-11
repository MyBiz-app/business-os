"""The owner's default staff-scheduling view.

Like the schedule board (0060): the owner picks how the shifts board opens (people or branches
side by side, the range, the branches) and it opens that way for everyone. No range stored means
the first branch's planning rhythm decides, as before.

Revision ID: 0064
Revises: 0063
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("shifts_default_view", "shifts_default_range", "shifts_default_branches")


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN shifts_default_view text NOT NULL DEFAULT 'people'
                CHECK (shifts_default_view IN ('people', 'branches')),
            ADD COLUMN shifts_default_range text
                CHECK (shifts_default_range IN ('day', 'week', 'month', 'custom')),
            ADD COLUMN shifts_default_branches uuid[] NOT NULL DEFAULT '{}'
                CHECK (cardinality(shifts_default_branches) <= 3)
    """)
    op.execute(f"GRANT UPDATE ({', '.join(COLUMNS)}) ON app.tenants TO app_api")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN shifts_default_branches, DROP COLUMN shifts_default_range,
            DROP COLUMN shifts_default_view
    """)
