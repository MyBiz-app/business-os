"""Catalog: locations with rooms, and services (what the business sells and schedules).

A service is vertical-agnostic: a class has capacity N, an appointment capacity 1.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("locations", "rooms", "services")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.locations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name        text NOT NULL CHECK (length(trim(name)) > 0),
            address     text,
            active      boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    # Composite foreign key: a room can only belong to a location of the same tenant.
    op.execute("""
        CREATE TABLE app.rooms (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL,
            location_id  uuid NOT NULL,
            name         text NOT NULL CHECK (length(trim(name)) > 0),
            capacity     integer CHECK (capacity > 0),
            active       boolean NOT NULL DEFAULT true,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, location_id)
                REFERENCES app.locations (tenant_id, id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX rooms_location_idx ON app.rooms (tenant_id, location_id)")
    # Money is integer minor units (agorot, cents) plus an ISO 4217 currency code.
    op.execute("""
        CREATE TABLE app.services (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name              text NOT NULL CHECK (length(trim(name)) > 0),
            description       text,
            duration_minutes  integer NOT NULL CHECK (duration_minutes BETWEEN 5 AND 1440),
            capacity          integer NOT NULL DEFAULT 1 CHECK (capacity BETWEEN 1 AND 1000),
            price_amount      integer NOT NULL DEFAULT 0 CHECK (price_amount >= 0),
            price_currency    char(3) NOT NULL,
            color             text CHECK (color ~ '^#[0-9a-fA-F]{6}$'),
            active            boolean NOT NULL DEFAULT true,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX services_tenant_idx ON app.services (tenant_id, name)")

    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.services, app.rooms, app.locations")
