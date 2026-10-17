"""Background jobs at scale (go-live GL14).

Each run of a job now records how many businesses it handled and how many failed, so one
business that keeps failing is visible without stopping the others. A message that could not be
sent waits longer after every attempt (`next_attempt_at`), and a partial index keeps the outbox
scan quick when the table holds millions of sent messages.

Revision ID: 0116
Revises: 0115
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0116"
down_revision: str | None = "0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.job_runs
            ADD COLUMN succeeded integer NOT NULL DEFAULT 0,
            ADD COLUMN failed integer NOT NULL DEFAULT 0
    """)
    op.execute("ALTER TABLE app.messages ADD COLUMN next_attempt_at timestamptz")
    op.execute("""
        CREATE INDEX messages_outbox ON app.messages (created_at)
            WHERE status = 'queued'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX app.messages_outbox")
    op.execute("ALTER TABLE app.messages DROP COLUMN next_attempt_at")
    op.execute("ALTER TABLE app.job_runs DROP COLUMN succeeded, DROP COLUMN failed")
