"""Client profile by industry and a visit log.

Each vertical pack defines extra client fields (a garage: the car's plate, make and model; a
clinic: ID number and health fund; ...); their values live in clients.custom_fields and the API
validates them against the pack. Visit notes are a per-client log written by staff (a clinic's
treatment notes, a garage's service history, a trainer's notes), optionally about a booking.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.clients ADD COLUMN custom_fields jsonb NOT NULL DEFAULT '{}'
            CHECK (jsonb_typeof(custom_fields) = 'object')
    """)

    op.execute("""
        CREATE TABLE app.client_notes (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id       uuid NOT NULL,
            booking_id      uuid REFERENCES app.bookings (id) ON DELETE SET NULL,
            author_user_id  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 5000),
            created_at      timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX client_notes_client ON app.client_notes (client_id, created_at)")
    op.execute("GRANT SELECT, INSERT, DELETE ON app.client_notes TO app_api")
    op.execute("ALTER TABLE app.client_notes ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY client_notes_tenant ON app.client_notes TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.client_notes")
    op.execute("ALTER TABLE app.clients DROP COLUMN custom_fields")
