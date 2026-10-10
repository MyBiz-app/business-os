"""Stations: the named rooms, desks or posts of a branch that shifts are planned into.

A fitness studio has "Pilates 1", "Pilates 2" and "Yoga 2"; a restaurant has "Kitchen" and
"Till". The owner defines them per branch and a shift may name one (`shifts.station_id`), so the
roster says who works where, with several people on one station when it is busy. A shift without
a station keeps working as before. A station always belongs to the shift's own branch (the foreign
key carries the branch), and deleting a station only clears it from its shifts.

Revision ID: 0066
Revises: 0065
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.stations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id uuid NOT NULL,
            name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
            sort_order  smallint NOT NULL DEFAULT 0,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, location_id, name),
            UNIQUE (tenant_id, location_id, id),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.stations TO app_api")
    op.execute("ALTER TABLE app.stations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY stations_tenant ON app.stations TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("ALTER TABLE app.shifts ADD COLUMN station_id uuid")
    op.execute("""
        ALTER TABLE app.shifts ADD CONSTRAINT shifts_station_fk
            FOREIGN KEY (tenant_id, location_id, station_id)
            REFERENCES app.stations (tenant_id, location_id, id)
            ON DELETE SET NULL (station_id)
    """)
    op.execute("CREATE INDEX shifts_station ON app.shifts (tenant_id, station_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE app.shifts DROP COLUMN station_id")
    op.execute("DROP TABLE app.stations")
