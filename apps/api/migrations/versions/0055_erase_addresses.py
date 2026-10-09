"""Erasing a client removes their addresses (privacy review, #51).

Addresses were only ever deactivated, so the API had no right to delete them; a privacy
erasure needs it. Row-level security still limits it to the business's own clients.

Revision ID: 0055
Revises: 0054
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT DELETE ON app.client_addresses TO app_api")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON app.client_addresses FROM app_api")
