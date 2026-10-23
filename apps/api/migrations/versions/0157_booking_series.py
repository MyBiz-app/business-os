"""Booking series: a standing weekly booking, or a course joined once (slice C5).

A series is the client's wish ("every Tuesday 19:00 on court 2, for 12 weeks"). The sessions and
bookings it produces are ordinary rows, each booking pointing back to its series, so every screen
and report keeps working and one cancel can release the rest. Expand step: a new table and one new
nullable column, nothing existing changes.

Revision ID: 0157
Revises: 0156
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0157"
down_revision: str | None = "0156"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.booking_series (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id        uuid NOT NULL,
            kind             text NOT NULL CHECK (kind IN ('resource', 'appointment', 'class')),
            service_id       uuid NOT NULL,
            room_id          uuid,
            staff_user_id    uuid,
            dependent_id     uuid,
            first_starts_at  timestamptz NOT NULL,
            minutes          integer CHECK (minutes IS NULL OR minutes BETWEEN 15 AND 1440),
            every_weeks      smallint NOT NULL DEFAULT 1 CHECK (every_weeks BETWEEN 1 AND 4),
            occurrences      smallint NOT NULL CHECK (occurrences BETWEEN 2 AND 52),
            status           text NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'cancelled')),
            cancelled_at     timestamptz,
            created_by       uuid,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id),
            FOREIGN KEY (tenant_id, service_id) REFERENCES app.services (tenant_id, id),
            FOREIGN KEY (tenant_id, room_id) REFERENCES app.rooms (tenant_id, id),
            -- a resource series needs a room and a length, an appointment series needs staff
            CHECK (kind <> 'resource' OR (room_id IS NOT NULL AND minutes IS NOT NULL)),
            CHECK (kind <> 'appointment' OR staff_user_id IS NOT NULL)
        )
    """)
    op.execute("CREATE INDEX booking_series_client ON app.booking_series (tenant_id, client_id)")
    op.execute("CREATE INDEX booking_series_service ON app.booking_series (tenant_id, service_id)")
    op.execute(
        "CREATE INDEX booking_series_room ON app.booking_series (tenant_id, room_id)"
        " WHERE room_id IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE app.bookings ADD COLUMN series_id uuid REFERENCES app.booking_series (id)"
    )
    op.execute(
        "CREATE INDEX bookings_series ON app.bookings (series_id) WHERE series_id IS NOT NULL"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE ON app.booking_series TO app_api")
    op.execute("ALTER TABLE app.booking_series ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY booking_series_tenant ON app.booking_series TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # A client sees and manages their own series in the app.
    op.execute("""
        CREATE POLICY booking_series_client ON app.booking_series TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)
