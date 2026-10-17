"""Monthly payroll runs up to gross pay (round 6, P4).

- `payroll_runs`: one run per business and month. It moves through the stages hours (the month's
  clocked hours are checked and locked), additions (bonuses and one-off amounts), review (every
  warning is fixed or acknowledged) and approved (only the owner; the month is then locked).
  Payslips stay marked as drafts until an accountant has checked the run (`accountant_checked_at`).
- `payroll_run_lines`: one row per person, a snapshot of the gross pay worked out when the run was
  built or refreshed: the base, overtime, fixed components and one-off amounts, each line with its
  source in `items` ("why this amount"), the warnings and what the payroll manager typed in
  (`inputs`: amounts of components typed each month, acknowledged warnings).
  Net pay, payslips and the bank file come later (P5).

Revision ID: 0109
Revises: 0110
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0109"
down_revision: str | None = "0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.payroll_runs (
            id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id             uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            period                date NOT NULL CHECK (period = date_trunc('month', period)::date),
            stage                 text NOT NULL DEFAULT 'hours'
                CHECK (stage IN ('hours', 'additions', 'review', 'approved')),
            currency              text NOT NULL DEFAULT 'ILS' CHECK (currency ~ '^[A-Z]{3}$'),
            created_by            uuid REFERENCES app.users (id) ON DELETE SET NULL,
            hours_locked_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            hours_locked_at       timestamptz,
            reviewed_by           uuid REFERENCES app.users (id) ON DELETE SET NULL,
            reviewed_at           timestamptz,
            approved_by           uuid REFERENCES app.users (id) ON DELETE SET NULL,
            approved_at           timestamptz,
            accountant_checked_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            accountant_checked_at timestamptz,
            export_file_id        uuid,
            created_at            timestamptz NOT NULL DEFAULT now(),
            updated_at            timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, period),
            CHECK ((stage = 'approved') = (approved_at IS NOT NULL))
        )
    """)
    for column in ("created_by", "hours_locked_by", "reviewed_by", "approved_by"):
        op.execute(f"CREATE INDEX payroll_runs_{column}_fk ON app.payroll_runs ({column})")
    op.execute(
        "CREATE INDEX payroll_runs_accountant_checked_by_fk"
        " ON app.payroll_runs (accountant_checked_by)"
    )
    op.execute("""
        CREATE TABLE app.payroll_run_lines (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            run_id                  uuid NOT NULL REFERENCES app.payroll_runs (id)
                ON DELETE CASCADE,
            user_id                 uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            employment_type         text NOT NULL DEFAULT 'global'
                CHECK (employment_type IN ('global', 'hourly', 'global_overtime')),
            hours_total             numeric(7, 2) NOT NULL DEFAULT 0,
            hours_regular           numeric(7, 2) NOT NULL DEFAULT 0,
            hours_tier1             numeric(7, 2) NOT NULL DEFAULT 0,
            hours_tier2             numeric(7, 2) NOT NULL DEFAULT 0,
            hours_rest_day          numeric(7, 2) NOT NULL DEFAULT 0,
            work_days               integer NOT NULL DEFAULT 0,
            base_minor              bigint NOT NULL DEFAULT 0,
            overtime_minor          bigint NOT NULL DEFAULT 0,
            components_minor        bigint NOT NULL DEFAULT 0,
            adjustments_minor       bigint NOT NULL DEFAULT 0,
            deductions_minor        bigint NOT NULL DEFAULT 0,
            gross_minor             bigint NOT NULL DEFAULT 0,
            taxable_minor           bigint NOT NULL DEFAULT 0,
            social_security_minor   bigint NOT NULL DEFAULT 0,
            pension_base_minor      bigint NOT NULL DEFAULT 0,
            items                   jsonb NOT NULL DEFAULT '[]',
            warnings                jsonb NOT NULL DEFAULT '[]',
            inputs                  jsonb NOT NULL DEFAULT '{}',
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE (run_id, user_id)
        )
    """)
    op.execute("CREATE INDEX payroll_run_lines_tenant ON app.payroll_run_lines (tenant_id)")
    op.execute("CREATE INDEX payroll_run_lines_user_fk ON app.payroll_run_lines (user_id)")
    for table in ("payroll_runs", "payroll_run_lines"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.payroll_run_lines")
    op.execute("DROP TABLE app.payroll_runs")
