"""Records when a business's welcome email went out, so it is sent once.

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN welcome_sent_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE app.tenants DROP COLUMN welcome_sent_at")
