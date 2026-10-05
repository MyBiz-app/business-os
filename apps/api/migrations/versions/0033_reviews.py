"""Reviews: after a visit the client rates it (1-5 stars, optional comment) in the app.

One review per attended booking. The review records the service and the staff member who led
the session at the time, so satisfaction can be reported per service and per staff member.
Clients insert their own reviews (RLS checks the client); the API checks the booking is theirs,
was attended and is recent.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.reviews (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id      uuid NOT NULL,
            booking_id     uuid NOT NULL UNIQUE REFERENCES app.bookings (id) ON DELETE CASCADE,
            service_id     uuid NOT NULL REFERENCES app.services (id) ON DELETE CASCADE,
            staff_user_id  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            rating         smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment        text CHECK (length(comment) <= 1000),
            created_at     timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX reviews_tenant ON app.reviews (tenant_id, created_at)")
    op.execute("CREATE INDEX reviews_client ON app.reviews (client_id)")
    op.execute("GRANT SELECT, INSERT, DELETE, UPDATE (comment) ON app.reviews TO app_api")
    op.execute("ALTER TABLE app.reviews ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY reviews_tenant ON app.reviews TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY reviews_client_select ON app.reviews FOR SELECT TO app_api
        USING (client_id = app.current_client_id())
    """)
    op.execute("""
        CREATE POLICY reviews_client_insert ON app.reviews FOR INSERT TO app_api
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.reviews")
