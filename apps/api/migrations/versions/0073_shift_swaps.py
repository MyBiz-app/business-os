"""Shift swaps: a person offers one of their shifts to a colleague, a manager approves.

The shift only changes hands on the manager's approval, by the normal edit of `shifts.user_id`,
so the roster-change trigger and emails (0069) cover the notification.

Revision ID: 0073
Revises: 0072
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.shift_swaps (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            shift_id          uuid NOT NULL REFERENCES app.shifts (id) ON DELETE CASCADE,
            from_user_id      uuid NOT NULL,
            to_user_id        uuid NOT NULL,
            note              text CHECK (char_length(note) <= 200),
            status            text NOT NULL DEFAULT 'pending_colleague'
                              CHECK (status IN ('pending_colleague', 'pending_manager',
                                                'approved', 'declined', 'refused', 'cancelled')),
            colleague_at      timestamptz,
            decided_by        uuid,
            decided_at        timestamptz,
            decision_note     text CHECK (char_length(decision_note) <= 200),
            created_at        timestamptz NOT NULL DEFAULT now(),
            CHECK (from_user_id <> to_user_id),
            FOREIGN KEY (tenant_id, from_user_id)
                REFERENCES app.tenant_members (tenant_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, to_user_id)
                REFERENCES app.tenant_members (tenant_id, user_id) ON DELETE CASCADE
        )
    """)
    # One open swap per shift.
    op.execute(
        "CREATE UNIQUE INDEX shift_swaps_open ON app.shift_swaps (shift_id)"
        " WHERE status IN ('pending_colleague', 'pending_manager')"
    )
    op.execute("CREATE INDEX shift_swaps_tenant ON app.shift_swaps (tenant_id, status, created_at)")
    op.execute("CREATE INDEX shift_swaps_from ON app.shift_swaps (tenant_id, from_user_id)")
    op.execute("CREATE INDEX shift_swaps_to ON app.shift_swaps (tenant_id, to_user_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.shift_swaps TO app_api")
    op.execute("ALTER TABLE app.shift_swaps ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY shift_swaps_tenant ON app.shift_swaps TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.shift_swaps")
