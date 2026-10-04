"""Email delivery state for client notifications (sent by the send-emails job).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.notifications
            ADD COLUMN email_status text NOT NULL DEFAULT 'pending'
                CHECK (email_status IN ('pending', 'sent', 'failed', 'skipped')),
            ADD COLUMN email_attempts smallint NOT NULL DEFAULT 0,
            ADD COLUMN emailed_at timestamptz
    """)
    # Everything recorded before email existed is history, not news.
    op.execute("UPDATE app.notifications SET email_status = 'skipped'")
    op.execute(
        "CREATE INDEX notifications_email_pending_idx ON app.notifications (created_at) "
        "WHERE email_status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX app.notifications_email_pending_idx")
    op.execute("""
        ALTER TABLE app.notifications
            DROP COLUMN emailed_at, DROP COLUMN email_attempts, DROP COLUMN email_status
    """)
