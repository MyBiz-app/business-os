"""Dependents (#43, decision X10): pets under an owner, children under a parent.

A dependent is a profile under a client: who actually comes (Rex the dog, Noa the daughter),
while the client books and pays. A booking can name one of its client's dependents; a client
can then hold one live booking per session *and dependent* (two children in the same class).
Clients see and manage their own dependents in the app; staff manage everyone's.

Revision ID: 0046
Revises: 0045
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NONE = "'00000000-0000-0000-0000-000000000000'::uuid"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.dependents (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid NOT NULL,
            kind        text NOT NULL CHECK (kind IN ('pet', 'child')),
            name        text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
            birth_date  date,
            details     jsonb NOT NULL DEFAULT '{}',
            notes       text CHECK (length(notes) <= 2000),
            active      boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, client_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX dependents_client ON app.dependents (tenant_id, client_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.dependents TO app_api")
    op.execute("ALTER TABLE app.dependents ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY dependents_tenant ON app.dependents TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # A client manages their own pets / children in the app.
    op.execute("""
        CREATE POLICY dependents_client ON app.dependents TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)

    # A booking can name one of its client's dependents (the composite key makes sure of that).
    op.execute("ALTER TABLE app.bookings ADD COLUMN dependent_id uuid")
    op.execute("""
        ALTER TABLE app.bookings ADD CONSTRAINT bookings_dependent_fkey
        FOREIGN KEY (tenant_id, client_id, dependent_id)
        REFERENCES app.dependents (tenant_id, client_id, id) ON DELETE SET NULL (dependent_id)
    """)
    op.execute("CREATE INDEX bookings_dependent ON app.bookings (dependent_id)")
    op.execute("DROP INDEX app.bookings_session_client_key")
    op.execute(f"""
        CREATE UNIQUE INDEX bookings_session_client_key
        ON app.bookings (session_id, client_id, coalesce(dependent_id, {NONE}))
        WHERE status <> 'cancelled'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX app.bookings_session_client_key")
    op.execute("DELETE FROM app.bookings WHERE dependent_id IS NOT NULL AND status <> 'cancelled'")
    op.execute("""
        CREATE UNIQUE INDEX bookings_session_client_key ON app.bookings (session_id, client_id)
        WHERE status <> 'cancelled'
    """)
    op.execute("DROP INDEX app.bookings_dependent")
    op.execute("ALTER TABLE app.bookings DROP CONSTRAINT bookings_dependent_fkey")
    op.execute("ALTER TABLE app.bookings DROP COLUMN dependent_id")
    op.execute("DROP TABLE app.dependents")
