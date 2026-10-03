"""Schedule: sessions (one occurrence of a service at a time), optionally from a weekly series.

A session is the vertical-agnostic "session with capacity": capacity 1 is an appointment,
N is a class. Times are stored as timestamptz (UTC); series keep the local wall-clock time
and are expanded in the tenant's time zone, so daylight-saving changes keep 18:00 at 18:00.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Targets for composite foreign keys, so references can never cross tenants.
    op.execute(
        "ALTER TABLE app.services ADD CONSTRAINT services_tenant_id_key UNIQUE (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE app.rooms ADD CONSTRAINT rooms_tenant_location_id_key "
        "UNIQUE (tenant_id, location_id, id)"
    )

    common_columns = """
        service_id          uuid NOT NULL,
        location_id         uuid,
        room_id             uuid,
        instructor_user_id  uuid,
        capacity            integer NOT NULL CHECK (capacity BETWEEN 1 AND 1000),
    """
    common_keys = """
        FOREIGN KEY (tenant_id, service_id) REFERENCES app.services (tenant_id, id),
        FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id),
        FOREIGN KEY (tenant_id, location_id, room_id)
            REFERENCES app.rooms (tenant_id, location_id, id),
        FOREIGN KEY (tenant_id, instructor_user_id)
            REFERENCES app.tenant_members (tenant_id, user_id)
            ON DELETE SET NULL (instructor_user_id),
        CHECK (room_id IS NULL OR location_id IS NOT NULL)
    """
    op.execute(f"""
        CREATE TABLE app.session_series (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            {common_columns}
            weekdays          smallint[] NOT NULL
                              CHECK (cardinality(weekdays) > 0 AND weekdays <@ '{{0,1,2,3,4,5,6}}'),
            start_time        time NOT NULL,
            duration_minutes  integer NOT NULL CHECK (duration_minutes BETWEEN 5 AND 1440),
            starts_on         date NOT NULL,
            ends_on           date NOT NULL CHECK (ends_on >= starts_on),
            created_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            {common_keys}
        )
    """)
    op.execute(f"""
        CREATE TABLE app.sessions (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            series_id   uuid,
            {common_columns}
            starts_at   timestamptz NOT NULL,
            ends_at     timestamptz NOT NULL CHECK (ends_at > starts_at),
            status      text NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled', 'cancelled')),
            notes       text,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, series_id) REFERENCES app.session_series (tenant_id, id)
                ON DELETE SET NULL (series_id),
            {common_keys}
        )
    """)
    op.execute("CREATE INDEX sessions_tenant_starts_idx ON app.sessions (tenant_id, starts_at)")
    # A series never produces the same occurrence twice.
    op.execute(
        "CREATE UNIQUE INDEX sessions_series_start_key ON app.sessions (series_id, starts_at)"
    )

    for table in ("session_series", "sessions"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.sessions, app.session_series")
    op.execute("ALTER TABLE app.rooms DROP CONSTRAINT rooms_tenant_location_id_key")
    op.execute("ALTER TABLE app.services DROP CONSTRAINT services_tenant_id_key")
