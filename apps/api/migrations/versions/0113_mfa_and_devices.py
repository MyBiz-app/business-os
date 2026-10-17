"""Two-step sign-in (MFA) and known devices (go-live, GL1).

A business can require every member of its team to sign in with an authenticator code
(`tenants.require_mfa_for_staff`). `login_devices` remembers the devices a person signed in from,
so a sign-in from a new one can be emailed to them and the recent ones listed in their account.
Only a hash of the device id is kept. Not tenant-scoped: it belongs to the person.

Revision ID: 0113
Revises: 0112
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0113"
down_revision: str | None = "0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.tenants ADD COLUMN require_mfa_for_staff boolean NOT NULL DEFAULT false"
    )
    op.execute("GRANT UPDATE (require_mfa_for_staff) ON app.tenants TO app_api")
    op.execute("""
        CREATE TABLE app.login_devices (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            device_hash   text NOT NULL,
            label         text NOT NULL DEFAULT '',
            first_seen_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, device_hash)
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.login_devices TO app_api")
    op.execute("ALTER TABLE app.login_devices ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY login_devices_self ON app.login_devices TO app_api
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.login_devices")
    op.execute("ALTER TABLE app.tenants DROP COLUMN require_mfa_for_staff")
