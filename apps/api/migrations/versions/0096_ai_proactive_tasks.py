"""Proactive agent behaviours: the morning briefing and opt-in suggestions (round 5, A8).

These are ordinary scheduled tasks (0092) that the system files for a person who switched the
behaviour on in the AI team page. `system_key` marks them, so each person has at most one of
each and the board can show them with their own name.

Revision ID: 0096
Revises: 0092
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0096"
down_revision: str | None = "0092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.ai_scheduled_tasks
        ADD COLUMN system_key text CHECK (system_key IN ('morning_briefing', 'suggestions'))
    """)
    op.execute(
        "CREATE UNIQUE INDEX ai_scheduled_tasks_system_idx ON app.ai_scheduled_tasks "
        "(tenant_id, created_by, system_key) WHERE system_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX app.ai_scheduled_tasks_system_idx")
    op.execute("ALTER TABLE app.ai_scheduled_tasks DROP COLUMN system_key")
