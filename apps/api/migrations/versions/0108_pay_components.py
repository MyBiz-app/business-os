"""Pay components, one-off adjustments (bonuses) and the dated rates table (round 6, P3).

- `payroll_rates`: law-driven rates (minimum wage, overtime tiers, credit point value, pension
  defaults) valid from a date, the same for every business. Read-only for the API; filled by
  migrations, and every row says where it came from and whether an accountant verified it. The
  seed rows are examples to be verified before payroll is switched on.
- `pay_components`: the fixed monthly components of a team member (travel, meals, phone, car, a
  fixed addition, recuperation, a fixed deduction). Each says whether it is taxable, liable to
  national insurance and part of the pension base (defaults come from the kind).
- `pay_adjustments`: one-off additions and deductions for a month (bonus, holiday gift, expense
  refund, deduction). A branch manager only proposes (`proposed`); the owner approves.

Revision ID: 0108
Revises: 0106
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0108"
down_revision: str | None = "0106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXAMPLE = "example from the round 6 spec, to be verified by an accountant"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.payroll_rates (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            rate_key    text NOT NULL CHECK (length(trim(rate_key)) > 0),
            valid_from  date NOT NULL,
            value       jsonb NOT NULL,
            source      text NOT NULL CHECK (length(trim(source)) > 0),
            verified_at timestamptz,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (rate_key, valid_from)
        )
    """)
    op.execute("GRANT SELECT ON app.payroll_rates TO app_api")
    op.execute("ALTER TABLE app.payroll_rates ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY payroll_rates_read ON app.payroll_rates FOR SELECT TO app_api USING (true)"
    )
    op.execute(f"""
        INSERT INTO app.payroll_rates (rate_key, valid_from, value, source) VALUES
        ('min_wage_monthly', '2025-04-01', '{{"minor": 624767, "currency": "ILS"}}', '{EXAMPLE}'),
        ('min_wage_hourly', '2025-04-01', '{{"minor": 3432, "currency": "ILS"}}', '{EXAMPLE}'),
        ('weekly_hours', '2025-01-01', '{{"hours": 42}}', '{EXAMPLE}'),
        ('overtime_tiers', '2025-01-01',
         '{{"tiers": [{{"hours": 2, "pct": 125}}, {{"hours": null, "pct": 150}}]}}', '{EXAMPLE}'),
        ('credit_point_monthly', '2025-01-01', '{{"minor": 24200, "currency": "ILS"}}', '{EXAMPLE}'),
        ('pension_defaults', '2025-01-01',
         '{{"employee_pct": 6, "employer_pct": 6.5, "severance_pct": 6}}', '{EXAMPLE}')
    """)

    op.execute("""
        CREATE TABLE app.pay_components (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id                 uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            kind                    text NOT NULL CHECK (kind IN (
                'travel', 'meals', 'phone', 'car', 'fixed_addition', 'recuperation',
                'fixed_deduction')),
            name                    text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
            calc                    text NOT NULL CHECK (calc IN (
                'per_work_day', 'monthly', 'by_month', 'automatic')),
            amount_minor            bigint CHECK (amount_minor >= 0),
            cap_minor               bigint CHECK (cap_minor >= 0),
            currency                text NOT NULL DEFAULT 'ILS' CHECK (currency ~ '^[A-Z]{3}$'),
            taxable                 boolean NOT NULL,
            social_security_liable  boolean NOT NULL,
            pension_base            boolean NOT NULL,
            valid_from              date NOT NULL DEFAULT current_date,
            valid_to                date,
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            CHECK (valid_to IS NULL OR valid_to >= valid_from),
            CHECK (calc IN ('by_month', 'automatic') OR amount_minor IS NOT NULL)
        )
    """)
    op.execute("CREATE INDEX pay_components_member ON app.pay_components (tenant_id, user_id)")
    op.execute("CREATE INDEX pay_components_user_fk ON app.pay_components (user_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.pay_components TO app_api")
    op.execute("ALTER TABLE app.pay_components ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pay_components_tenant ON app.pay_components TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.pay_adjustments (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id                 uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            period                  date NOT NULL CHECK (extract(day FROM period) = 1),
            kind                    text NOT NULL CHECK (kind IN (
                'bonus', 'holiday_gift', 'expense_refund', 'deduction')),
            amount_minor            bigint NOT NULL CHECK (amount_minor > 0),
            currency                text NOT NULL DEFAULT 'ILS' CHECK (currency ~ '^[A-Z]{3}$'),
            note                    text CHECK (length(note) <= 200),
            taxable                 boolean NOT NULL,
            social_security_liable  boolean NOT NULL,
            pension_base            boolean NOT NULL,
            status                  text NOT NULL DEFAULT 'approved'
                CHECK (status IN ('proposed', 'approved', 'rejected')),
            batch_id                uuid NOT NULL DEFAULT gen_random_uuid(),
            proposed_by             uuid REFERENCES app.users (id) ON DELETE SET NULL,
            decided_by              uuid REFERENCES app.users (id) ON DELETE SET NULL,
            decided_at              timestamptz,
            created_by              uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at              timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX pay_adjustments_period ON app.pay_adjustments (tenant_id, period, status)"
    )
    op.execute("CREATE INDEX pay_adjustments_user_fk ON app.pay_adjustments (user_id)")
    op.execute("CREATE INDEX pay_adjustments_proposed_by_fk ON app.pay_adjustments (proposed_by)")
    op.execute("CREATE INDEX pay_adjustments_decided_by_fk ON app.pay_adjustments (decided_by)")
    op.execute("CREATE INDEX pay_adjustments_created_by_fk ON app.pay_adjustments (created_by)")
    op.execute("CREATE INDEX pay_adjustments_batch ON app.pay_adjustments (tenant_id, batch_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.pay_adjustments TO app_api")
    op.execute("ALTER TABLE app.pay_adjustments ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pay_adjustments_tenant ON app.pay_adjustments TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.pay_adjustments")
    op.execute("DROP TABLE app.pay_components")
    op.execute("DROP TABLE app.payroll_rates")
