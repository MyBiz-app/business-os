"""Time-off requests: a staff member asks for days off, a manager approves or declines.

An approved request creates the same `staff_time_off` row a manager would add by hand, so the
board, the booking engine and the coverage rules need no change.

Revision ID: 0071
Revises: 0070
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.time_off_requests (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id       uuid NOT NULL,
            starts_on     date NOT NULL,
            ends_on       date NOT NULL,
            reason        text CHECK (char_length(reason) <= 200),
            status        text NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'approved', 'declined', 'cancelled')),
            decided_by    uuid,
            decided_at    timestamptz,
            decision_note text CHECK (char_length(decision_note) <= 200),
            time_off_id   uuid REFERENCES app.staff_time_off (id) ON DELETE SET NULL,
            created_at    timestamptz NOT NULL DEFAULT now(),
            CHECK (ends_on >= starts_on AND ends_on - starts_on <= 366),
            FOREIGN KEY (tenant_id, user_id)
                REFERENCES app.tenant_members (tenant_id, user_id) ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX time_off_requests_tenant ON app.time_off_requests"
        " (tenant_id, status, starts_on)"
    )
    op.execute("CREATE INDEX time_off_requests_user ON app.time_off_requests (user_id, starts_on)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.time_off_requests TO app_api")
    op.execute("ALTER TABLE app.time_off_requests ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY time_off_requests_tenant ON app.time_off_requests TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.time_off_requests")
