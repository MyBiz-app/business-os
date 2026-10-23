"""Several instructors for one class, and open entry (slice C6 of the categories spec).

- `session_instructors`: the instructors of a session besides the lead one that
  `sessions.instructor_user_id` already names (a tennis academy with 3 coaches and 24 kids).
- `session_series.extra_instructor_user_ids`: the same list for a weekly series, so the job that
  extends a series gives the new sessions the same team.
- `services.participants_per_instructor`: the ratio the business keeps (8 children per coach);
  a session's capacity may not exceed ratio x its instructors.
- `services.open_entry`: the service is entry to the place (open gym, pool, co-working), not a
  class. Its sessions are the opening hours; a client checks in against the plan and that is
  the booking.

This only adds.

Revision ID: 0158
Revises: 0157
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0158"
down_revision: str | None = "0157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.session_instructors (
            tenant_id   uuid NOT NULL,
            session_id  uuid NOT NULL,
            user_id     uuid NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (session_id, user_id),
            FOREIGN KEY (tenant_id, session_id)
                REFERENCES app.sessions (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, user_id)
                REFERENCES app.tenant_members (tenant_id, user_id) ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX session_instructors_user_idx ON app.session_instructors (tenant_id, user_id)"
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON app.session_instructors TO app_api")
    op.execute("ALTER TABLE app.session_instructors ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY session_instructors_tenant ON app.session_instructors TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        ALTER TABLE app.session_series
            ADD COLUMN extra_instructor_user_ids uuid[] NOT NULL DEFAULT '{}'
    """)
    op.execute("""
        ALTER TABLE app.services
            ADD COLUMN participants_per_instructor integer
                CHECK (participants_per_instructor BETWEEN 1 AND 1000),
            ADD COLUMN open_entry boolean NOT NULL DEFAULT false,
            ADD CONSTRAINT services_open_entry_class
                CHECK (NOT open_entry OR booking_mode = 'class')
    """)


def downgrade() -> None:
    # contract: only a rollback drops these, and the previous release never reads them.
    op.execute("""
        ALTER TABLE app.services
            DROP CONSTRAINT services_open_entry_class,
            DROP COLUMN open_entry, DROP COLUMN participants_per_instructor
    """)
    op.execute("ALTER TABLE app.session_series DROP COLUMN extra_instructor_user_ids")
    op.execute("DROP TABLE app.session_instructors")
