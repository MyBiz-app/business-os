"""Corrective payslips of approved payroll months (round 6, P6).

An approved month is locked. A mistake found afterwards is fixed with a corrective payslip: a new
version for one person and month that points at the one before it, carries the reason, the
adjustment lines and the net pay worked out again, and states the difference to pay or recover.
Nothing in the approved run is edited.

Revision ID: 0112
Revises: 0109
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0112"
down_revision: str | None = "0109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.payslip_corrections (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            run_id            uuid NOT NULL REFERENCES app.payroll_runs (id) ON DELETE CASCADE,
            user_id           uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            version           integer NOT NULL CHECK (version >= 1),
            supersedes_id     uuid REFERENCES app.payslip_corrections (id) ON DELETE SET NULL,
            reason            text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
            items             jsonb NOT NULL DEFAULT '[]',
            adjustment_minor  bigint NOT NULL,
            previous_net_minor bigint NOT NULL,
            difference_minor  bigint NOT NULL,
            net               jsonb NOT NULL,
            created_by        uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (run_id, user_id, version)
        )
    """)
    op.execute("CREATE INDEX payslip_corrections_tenant ON app.payslip_corrections (tenant_id)")
    op.execute("CREATE INDEX payslip_corrections_user_fk ON app.payslip_corrections (user_id)")
    op.execute(
        "CREATE INDEX payslip_corrections_supersedes_fk ON app.payslip_corrections (supersedes_id)"
    )
    op.execute(
        "CREATE INDEX payslip_corrections_created_by_fk ON app.payslip_corrections (created_by)"
    )
    op.execute("GRANT SELECT, INSERT ON app.payslip_corrections TO app_api")
    op.execute("ALTER TABLE app.payslip_corrections ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY payslip_corrections_tenant ON app.payslip_corrections TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.payslip_corrections")
