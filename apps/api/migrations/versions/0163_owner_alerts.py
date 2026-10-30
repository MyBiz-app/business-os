"""Phone alerts for the business owner (app sweep slice 14, improvement B14).

`owner_push_events` is a queue the hourly job fills from what clients did on their own (booked,
cancelled, joined a waitlist, joined the business, left an enquiry) and empties by sending one
push per owner. A row is unique per event, so running the job twice never sends twice. Only the
jobs role touches it. `owner_push_prefs` holds the kinds an owner switched off; a missing row
means the kind is on.

Revision ID: 0163
Revises: 0162
Create Date: 2026-10-30
"""

# contract: only the downgrade drops what this migration added; the upgrade just adds tables.

from collections.abc import Sequence

from alembic import op

revision: str = "0163"
down_revision: str | None = "0162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'booking_new', 'booking_cancelled', 'waitlist_joined', 'client_joined', 'lead_new'"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.owner_push_events (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            kind         text NOT NULL CHECK (kind IN ({KINDS})),
            ref_id       uuid NOT NULL,
            occurred_at  timestamptz NOT NULL,
            sent_at      timestamptz,
            UNIQUE (tenant_id, kind, ref_id)
        )
    """)
    op.execute(
        "CREATE INDEX owner_push_events_waiting ON app.owner_push_events (tenant_id) "
        "WHERE sent_at IS NULL"
    )
    # Written and read by the jobs role only (it bypasses row-level security). The API role has
    # no grant on the queue; the policy is there so that a later grant could never show another
    # business's rows.
    op.execute("ALTER TABLE app.owner_push_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY owner_push_events_tenant ON app.owner_push_events TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute(f"""
        CREATE TABLE app.owner_push_prefs (
            tenant_id  uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id    uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            kind       text NOT NULL CHECK (kind IN ({KINDS})),
            enabled    boolean NOT NULL,
            PRIMARY KEY (tenant_id, user_id, kind)
        )
    """)
    op.execute("CREATE INDEX owner_push_prefs_user ON app.owner_push_prefs (user_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.owner_push_prefs TO app_api")
    op.execute("ALTER TABLE app.owner_push_prefs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY owner_push_prefs_self ON app.owner_push_prefs TO app_api
        USING (tenant_id = app.current_tenant_id() AND user_id = app.current_user_id())
        WITH CHECK (tenant_id = app.current_tenant_id() AND user_id = app.current_user_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.owner_push_prefs")
    op.execute("DROP TABLE app.owner_push_events")
