"""Emailing staff when their roster is published.

A published shift is emailed once to the person it belongs to (`shifts.notified_at`); shifts
that are already published count as notified, so deploying this sends nothing. Each person can
turn the emails off for themselves (`users.email_roster`, on by default).

Revision ID: 0068
Revises: 0067
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.shifts ADD COLUMN notified_at timestamptz")
    op.execute("UPDATE app.shifts SET notified_at = now()")
    op.execute(
        "CREATE INDEX shifts_unnotified ON app.shifts (published_at)"
        " WHERE published_at IS NOT NULL AND notified_at IS NULL"
    )
    op.execute("ALTER TABLE app.users ADD COLUMN email_roster boolean NOT NULL DEFAULT true")


def downgrade() -> None:
    op.execute("ALTER TABLE app.users DROP COLUMN email_roster")
    op.execute("DROP INDEX app.shifts_unnotified")
    op.execute("ALTER TABLE app.shifts DROP COLUMN notified_at")
