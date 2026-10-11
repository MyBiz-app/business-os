"""Owners and managers can remove services, memberships and punch cards.

The API only deletes a row nothing refers to; otherwise it deactivates the row (the foreign
keys from sessions and entitlements refuse the delete), so history is never lost. The new
`catalog.delete` permission is checked by the API; this only lets the API role issue DELETE.

Revision ID: 0061
Revises: 0060
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("services", "plans"):
        op.execute(f"GRANT DELETE ON app.{table} TO app_api")


def downgrade() -> None:
    for table in ("services", "plans"):
        op.execute(f"REVOKE DELETE ON app.{table} FROM app_api")
