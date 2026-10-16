"""Social connections waiting for the owner to pick accounts (Meta connector).

After the owner agrees on the network's page, the callback keeps what it found (encrypted, with
the tokens) for up to an hour until the owner chooses which accounts to connect.

Revision ID: 0095
Revises: 0093
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0095"
down_revision: str | None = "0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.social_pending (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            provider     text NOT NULL CHECK (length(provider) BETWEEN 1 AND 40),
            candidates   bytea NOT NULL,
            connected_by uuid,
            created_at   timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX social_pending_tenant ON app.social_pending (tenant_id, created_at)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.social_pending TO app_api")
    op.execute("ALTER TABLE app.social_pending ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY social_pending_tenant ON app.social_pending TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.social_pending")
