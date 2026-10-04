"""Class reminders: on the day of a class, booked clients get a "session_reminder"
notification (the remind-sessions job). bookings.reminded_at makes it once per booking.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
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
)


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


def upgrade() -> None:
    _kinds_check((*KINDS, "session_reminder"))
    op.execute("ALTER TABLE app.bookings ADD COLUMN reminded_at timestamptz")


def downgrade() -> None:
    op.execute("DELETE FROM app.notifications WHERE kind = 'session_reminder'")
    op.execute("ALTER TABLE app.bookings DROP COLUMN reminded_at")
    _kinds_check(KINDS)
