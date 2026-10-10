"""Shift scheduling for branch networks: a home branch per member, a planning rhythm per branch.

The home branch is informational (where the person normally works); it never limits where a
shift can be placed or what the person sees. The rhythm (daily, weekly, monthly or a custom
number of days) sets the window a branch's shift board opens on.

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


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenant_members
            ADD COLUMN home_location_id uuid,
            ADD CONSTRAINT tenant_members_home_location_fkey
                FOREIGN KEY (tenant_id, home_location_id)
                REFERENCES app.locations (tenant_id, id) ON DELETE SET NULL (home_location_id)
    """)
    op.execute("""
        ALTER TABLE app.locations
            ADD COLUMN planning_cadence text NOT NULL DEFAULT 'weekly'
                CHECK (planning_cadence IN ('daily', 'weekly', 'monthly', 'custom')),
            ADD COLUMN planning_days integer CHECK (planning_days BETWEEN 1 AND 42),
            ADD CONSTRAINT locations_planning_days_custom
                CHECK ((planning_cadence = 'custom') = (planning_days IS NOT NULL))
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE app.locations
            DROP CONSTRAINT locations_planning_days_custom,
            DROP COLUMN planning_days, DROP COLUMN planning_cadence
    """)
    op.execute("""
        ALTER TABLE app.tenant_members
            DROP CONSTRAINT tenant_members_home_location_fkey, DROP COLUMN home_location_id
    """)
