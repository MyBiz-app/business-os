"""Closing a business account: the owner closes it, the data is kept for 90 days, then deleted.

`tenants.closed_at` is set when the owner closes the business and cleared if they reopen it.
While it is set the business is locked (staff and client app get "business_closed"), no
automated jobs touch it and it is not billed. The delete-closed-businesses job removes the
business and everything under it once the grace period has passed (decision X20).

Revision ID: 0073
Revises: 0072
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN closed_at timestamptz")
    op.execute("GRANT UPDATE (closed_at) ON app.tenants TO app_api")  # only the closure endpoints
    op.execute(
        "CREATE INDEX tenants_closed_idx ON app.tenants (closed_at) WHERE closed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("REVOKE UPDATE (closed_at) ON app.tenants FROM app_api")
    op.execute("DROP INDEX app.tenants_closed_idx")
    op.execute("ALTER TABLE app.tenants DROP COLUMN closed_at")
