"""Staff can book a client over a class's capacity (round 7, R31).

Expand step: `app.bookings` gets `over_capacity` (the spot is beyond the class's capacity) with
who added it and when. Existing rows are false, so the previous release keeps working. Waitlist
promotion already counts every live booking against the capacity, so nobody is promoted while the
class is over it.

Revision ID: 0126
Revises: 0125
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0126"
down_revision: str | None = "0125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.bookings
            ADD COLUMN over_capacity boolean NOT NULL DEFAULT false,
            ADD COLUMN over_capacity_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            ADD COLUMN over_capacity_at timestamptz
    """)
    op.execute(
        "CREATE INDEX bookings_over_capacity_by ON app.bookings (over_capacity_by)"
        " WHERE over_capacity_by IS NOT NULL"
    )


def downgrade() -> None:
    # contract: only a rollback of this release drops the columns, and nothing else reads them
    op.execute("""
        ALTER TABLE app.bookings
            DROP COLUMN over_capacity_at,
            DROP COLUMN over_capacity_by,
            DROP COLUMN over_capacity
    """)
