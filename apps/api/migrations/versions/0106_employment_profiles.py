"""Employment terms and the digital Form 101 of team members (round 6, P1).

- `employment_profiles`: one row per team member with the terms of employment (global, hourly or
  global plus overtime), pension and study fund, and the bank account, which is kept encrypted
  with the platform secrets key (only the last four digits are readable).
- `form101_forms`: the yearly tax-credit declaration (Form 101). The answers are stored encrypted;
  the credit points are computed by the server from them and a payroll manager may correct them
  (`credit_points_override` with a note). The employee signs by typing their name; the signature
  time and name are kept with the form.

Revision ID: 0106
Revises: 0102
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0106"
down_revision: str | None = "0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.employment_profiles (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id                 uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            employment_type         text NOT NULL DEFAULT 'global'
                CHECK (employment_type IN ('global', 'hourly', 'global_overtime')),
            currency                text NOT NULL DEFAULT 'ILS' CHECK (currency ~ '^[A-Z]{3}$'),
            monthly_amount_minor    bigint CHECK (monthly_amount_minor >= 0),
            hourly_rate_minor       bigint CHECK (hourly_rate_minor >= 0),
            scope_pct               numeric(5, 2) NOT NULL DEFAULT 100
                CHECK (scope_pct > 0 AND scope_pct <= 100),
            start_date              date,
            work_days_per_week      smallint NOT NULL DEFAULT 5
                CHECK (work_days_per_week BETWEEN 1 AND 7),
            job_title               text CHECK (length(job_title) <= 120),
            billing_location_id     uuid,
            pension                 jsonb,
            study_fund              jsonb,
            employment_notice_date  date,
            bank_encrypted          bytea,
            bank_last4              text CHECK (length(bank_last4) BETWEEN 1 AND 4),
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id),
            FOREIGN KEY (tenant_id, billing_location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE SET NULL (billing_location_id)
        )
    """)
    op.execute(
        "CREATE INDEX employment_profiles_location"
        " ON app.employment_profiles (tenant_id, billing_location_id)"
    )
    op.execute("CREATE INDEX employment_profiles_user_fk ON app.employment_profiles (user_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.employment_profiles TO app_api")
    op.execute("ALTER TABLE app.employment_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY employment_profiles_tenant ON app.employment_profiles TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.form101_forms (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id                 uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            tax_year                smallint NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            status                  text NOT NULL DEFAULT 'requested'
                CHECK (status IN ('requested', 'submitted')),
            answers_encrypted       bytea,
            credit_points           numeric(5, 2),
            credit_points_override  numeric(5, 2) CHECK (credit_points_override >= 0),
            override_note           text CHECK (length(override_note) <= 500),
            requested_by            uuid REFERENCES app.users (id) ON DELETE SET NULL,
            requested_at            timestamptz NOT NULL DEFAULT now(),
            submitted_at            timestamptz,
            signed_name             text CHECK (length(signed_name) <= 160),
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id, tax_year),
            CHECK (status = 'requested' OR (answers_encrypted IS NOT NULL
                   AND submitted_at IS NOT NULL AND signed_name IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX form101_forms_user_fk ON app.form101_forms (user_id)")
    op.execute("CREATE INDEX form101_forms_requested_by_fk ON app.form101_forms (requested_by)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.form101_forms TO app_api")
    op.execute("ALTER TABLE app.form101_forms ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY form101_forms_tenant ON app.form101_forms TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.form101_forms")
    op.execute("DROP TABLE app.employment_profiles")
