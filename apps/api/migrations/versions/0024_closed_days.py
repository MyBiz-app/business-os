"""Closed days (holidays): dates a business is closed. Weekly series skip them, and closing a
day cancels its sessions.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.closed_days (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            day         date NOT NULL,
            reason      text CHECK (length(reason) <= 120),
            created_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, day)
        )
    """)
    op.execute("GRANT SELECT, INSERT, DELETE ON app.closed_days TO app_api")
    op.execute("ALTER TABLE app.closed_days ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY closed_days_tenant ON app.closed_days TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Clients see when their business is closed (the app's schedule).
    op.execute("""
        CREATE POLICY closed_days_client_select ON app.closed_days FOR SELECT TO app_api
        USING (tenant_id = app.client_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.closed_days")
