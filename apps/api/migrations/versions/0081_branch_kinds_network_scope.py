"""Branch kinds and the network policy.

A branch can be a sub-category of the business's category (a studio network with a pilates
branch and a crossfit branch). A business keeps its clients either for the whole network or per
branch: in the second case each client has a "my branches" list (`client_locations`).

Revision ID: 0081
Revises: 0080
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0081"
down_revision: str | None = "0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The kind is a catalog key; the API checks it is in the business's own category.
    op.execute(
        "ALTER TABLE app.locations ADD COLUMN kind text CHECK (length(kind) BETWEEN 1 AND 60)"
    )
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN network_scope text NOT NULL DEFAULT 'network'
                CHECK (network_scope IN ('network', 'branch'))
    """)
    op.execute("GRANT UPDATE (network_scope) ON app.tenants TO app_api")
    op.execute("""
        CREATE TABLE app.client_locations (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid NOT NULL,
            location_id uuid NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, client_id, location_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX client_locations_branch ON app.client_locations (tenant_id, location_id)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.client_locations TO app_api")
    op.execute("ALTER TABLE app.client_locations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY client_locations_tenant ON app.client_locations TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # A client with a home branch is already one of its clients.
    op.execute("""
        INSERT INTO app.client_locations (tenant_id, client_id, location_id)
        SELECT tenant_id, id, home_location_id FROM app.clients
        WHERE home_location_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.client_locations")
    op.execute("ALTER TABLE app.tenants DROP COLUMN network_scope")
    op.execute("ALTER TABLE app.locations DROP COLUMN kind")
