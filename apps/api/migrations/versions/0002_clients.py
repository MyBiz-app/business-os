"""Clients: the business's customers (members, in a fitness studio).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.clients (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            first_name     text NOT NULL CHECK (length(trim(first_name)) > 0),
            last_name      text,
            email          text,
            phone          text,
            date_of_birth  date,
            notes          text,
            status         text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'inactive', 'lead')),
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX clients_tenant_name_idx ON app.clients (tenant_id, first_name, last_name)"
    )
    # One client per email within a business; walk-ins without an email are allowed.
    op.execute("""
        CREATE UNIQUE INDEX clients_tenant_email_key
        ON app.clients (tenant_id, lower(email)) WHERE email IS NOT NULL
    """)

    op.execute("GRANT SELECT, INSERT, UPDATE ON app.clients TO app_api")
    op.execute("ALTER TABLE app.clients ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY clients_tenant ON app.clients TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.clients")
