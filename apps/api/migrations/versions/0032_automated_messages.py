"""Automated messages: reminders also go out over WhatsApp (simulated) when the business has
the messaging module. A message made from a notification records it, once per notification.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.messages
            ADD COLUMN notification_id uuid UNIQUE
                REFERENCES app.notifications (id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app.messages DROP COLUMN notification_id")
