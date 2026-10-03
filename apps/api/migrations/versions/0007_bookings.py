"""Bookings: a client's place in a session (booked, waitlisted, attended, cancelled).

Capacity is enforced by the API while holding a row lock on the session, so two concurrent
bookings can never both take the last spot. Waitlisted bookings are promoted in FIFO order
(`waitlisted_at`) when a spot opens.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Booking policy. Cancelling inside the window is allowed but recorded as a late cancel
    # (plans and punch cards will use it in Sprint 4). The default comes from the vertical pack.
    op.execute("""
        ALTER TABLE app.tenants
        ADD COLUMN cancellation_window_minutes integer NOT NULL DEFAULT 0
            CHECK (cancellation_window_minutes BETWEEN 0 AND 10080)
    """)
    op.execute(
        "ALTER TABLE app.clients ADD CONSTRAINT clients_tenant_id_key UNIQUE (tenant_id, id)"
    )

    op.execute("""
        CREATE TABLE app.bookings (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            session_id     uuid NOT NULL,
            client_id      uuid NOT NULL,
            status         text NOT NULL
                           CHECK (status IN ('booked', 'waitlisted', 'checked_in', 'no_show',
                                             'cancelled')),
            waitlisted_at  timestamptz,
            cancelled_at   timestamptz,
            late_cancel    boolean NOT NULL DEFAULT false,
            checked_in_at  timestamptz,
            created_by     uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, session_id) REFERENCES app.sessions (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            CHECK (status <> 'waitlisted' OR waitlisted_at IS NOT NULL),
            CHECK (status <> 'cancelled' OR cancelled_at IS NOT NULL)
        )
    """)
    # One live booking per client per session; cancelled rows are kept as history.
    op.execute("""
        CREATE UNIQUE INDEX bookings_session_client_key ON app.bookings (session_id, client_id)
        WHERE status <> 'cancelled'
    """)
    op.execute("CREATE INDEX bookings_session_idx ON app.bookings (session_id, status)")
    op.execute("CREATE INDEX bookings_client_idx ON app.bookings (tenant_id, client_id)")

    op.execute("GRANT SELECT, INSERT, UPDATE ON app.bookings TO app_api")
    op.execute("ALTER TABLE app.bookings ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY bookings_tenant ON app.bookings TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.bookings")
    op.execute("ALTER TABLE app.clients DROP CONSTRAINT clients_tenant_id_key")
    op.execute("ALTER TABLE app.tenants DROP COLUMN cancellation_window_minutes")
