"""The owner's default schedule view (docs/proposals/schedule-board-2026-10.md).

A business picks the range (day, week or month) and the branches its schedule opens with, so a
network sees its branches side by side without choosing them each time. No branches stored means
the branch picked in the menu applies, as before.

Revision ID: 0058
Revises: 0057
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("schedule_default_view", "schedule_default_branches")


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN schedule_default_view text NOT NULL DEFAULT 'week'
                CHECK (schedule_default_view IN ('day', 'week', 'month')),
            ADD COLUMN schedule_default_branches uuid[] NOT NULL DEFAULT '{}'
                CHECK (cardinality(schedule_default_branches) <= 3)
    """)
    op.execute(f"GRANT UPDATE ({', '.join(COLUMNS)}) ON app.tenants TO app_api")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN schedule_default_branches, DROP COLUMN schedule_default_view
    """)
