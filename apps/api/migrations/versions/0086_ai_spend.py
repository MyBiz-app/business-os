"""AI spend controls (round 5, A2): pay-as-you-go extra credits, per-role and per-person limits,
and the alerts raised as the month's use passes 80%, 100%, 150% and 200% of the included credits.

Pay-as-you-go is off by default. With it on, the business keeps working after its included credits
and the extra use becomes a line on the account; an optional cap (minor units of the business
currency) stops it. No cap means no limit.

Revision ID: 0086
Revises: 0085
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0086"
down_revision: str | None = "0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.tenant_ai_settings (
            tenant_id     uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            payg_enabled  boolean NOT NULL DEFAULT false,
            -- Most the business agrees to pay for extra credits in a month; null = no cap.
            payg_cap_minor integer CHECK (payg_cap_minor IS NULL OR payg_cap_minor >= 0),
            updated_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.ai_credit_limits (
            tenant_id       uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            subject_kind    text NOT NULL CHECK (subject_kind IN ('role', 'user')),
            subject_key     text NOT NULL,  -- a role key, or a user id
            monthly_credits integer NOT NULL CHECK (monthly_credits >= 0),
            PRIMARY KEY (tenant_id, subject_kind, subject_key)
        )
    """)
    op.execute("""
        CREATE TABLE app.ai_credit_alerts (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            month_start date NOT NULL,
            threshold   integer NOT NULL CHECK (threshold IN (80, 100, 150, 200)),
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, month_start, threshold)
        )
    """)
    for table in ("tenant_ai_settings", "ai_credit_limits", "ai_credit_alerts"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.ai_credit_alerts, app.ai_credit_limits, app.tenant_ai_settings")
