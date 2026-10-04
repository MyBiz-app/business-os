"""Client erasure: a client's personal details can be erased on request (privacy law).

The row stays so bookings, plans and payments keep their history (payments must be kept
for accounting); `erased_at` marks it, and the personal fields are cleared.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.clients ADD COLUMN erased_at timestamptz")
    # Health declarations are removed on erasure (they are health data, not records).
    op.execute("GRANT DELETE ON app.health_declarations TO app_api")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON app.health_declarations FROM app_api")
    op.execute("ALTER TABLE app.clients DROP COLUMN erased_at")
