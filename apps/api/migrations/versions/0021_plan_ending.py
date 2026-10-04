"""Plan-ending reminders: a client whose last valid plan ends in a few days gets a
"plan_ending" notification (the remind-plans job), once per plan.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
)


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


def upgrade() -> None:
    _kinds_check((*KINDS, "plan_ending"))
    op.execute("ALTER TABLE app.entitlements ADD COLUMN ending_notified_at timestamptz")


def downgrade() -> None:
    op.execute("DELETE FROM app.notifications WHERE kind = 'plan_ending'")
    op.execute("ALTER TABLE app.entitlements DROP COLUMN ending_notified_at")
    _kinds_check(KINDS)
