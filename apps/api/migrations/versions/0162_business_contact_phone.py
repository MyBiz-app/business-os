"""A business can publish a contact phone that clients can call or message on WhatsApp.

The client app shows "Call" and "WhatsApp" buttons on the business card when the owner has set
the number (settings > details). It is optional and empty by default; nothing is sent from the
platform, the buttons only open the phone's dialer or WhatsApp (app sweep slice 7, improvement C6).

Revision ID: 0162
Revises: 0161
Create Date: 2026-10-30
"""

# contract: only the downgrade drops what this migration added; the upgrade just adds a column.

from collections.abc import Sequence

from alembic import op

revision: str = "0162"
down_revision: str | None = "0161"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN contact_phone text")
    op.execute("GRANT UPDATE (contact_phone) ON app.tenants TO app_api")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (contact_phone) ON app.tenants FROM app_api")
    op.execute("ALTER TABLE app.tenants DROP COLUMN contact_phone")
