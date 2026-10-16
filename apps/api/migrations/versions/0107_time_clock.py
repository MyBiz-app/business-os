"""Time clock (round 6, P2): clock in and out, corrections, monthly approval, overtime rules.

- `time_clock_entries`: one row per stretch of work. A person clocks in and out themselves
  (`source = 'clock'`), or a manager adds or corrects a row with a written reason
  (`source = 'manual'`, `correction_reason`); every manager change is also written to the audit
  log. At most one open row (no `clock_out`) per person.
- `time_clock_approvals`: a manager approves a person's month; an approved month is locked until
  it is reopened.
- `time_clock_rules`: the overtime rules of a business (a row of its own, defaults in the
  columns), so the numbers live in data and not in code.

Revision ID: 0107
Revises: 0103
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0107"
down_revision: str | None = "0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.time_clock_entries (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id           uuid NOT NULL,
            location_id       uuid NOT NULL,
            shift_id          uuid REFERENCES app.shifts (id) ON DELETE SET NULL,
            clock_in          timestamptz NOT NULL,
            clock_out         timestamptz,
            source            text NOT NULL DEFAULT 'clock' CHECK (source IN ('clock', 'manual')),
            correction_reason text CHECK (length(correction_reason) <= 200),
            corrected_by      uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now(),
            CHECK (clock_out IS NULL OR clock_out > clock_in),
            CHECK (clock_out IS NULL OR clock_out - clock_in <= interval '24 hours'),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX time_clock_entries_open ON app.time_clock_entries"
        " (tenant_id, user_id) WHERE clock_out IS NULL"
    )
    op.execute(
        "CREATE INDEX time_clock_entries_user ON app.time_clock_entries"
        " (tenant_id, user_id, clock_in)"
    )
    op.execute(
        "CREATE INDEX time_clock_entries_location ON app.time_clock_entries"
        " (tenant_id, location_id)"
    )
    op.execute("CREATE INDEX time_clock_entries_shift ON app.time_clock_entries (shift_id)")
    op.execute(
        "CREATE INDEX time_clock_entries_corrected_by ON app.time_clock_entries (corrected_by)"
    )
    op.execute("""
        CREATE TABLE app.time_clock_approvals (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL,
            month       date NOT NULL CHECK (month = date_trunc('month', month)::date),
            approved_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            approved_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, user_id, month),
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX time_clock_approvals_approved_by ON app.time_clock_approvals (approved_by)"
    )
    op.execute("""
        CREATE TABLE app.time_clock_rules (
            tenant_id          uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            work_days_per_week integer NOT NULL DEFAULT 5 CHECK (work_days_per_week IN (5, 6)),
            week_hours         numeric(5, 2) NOT NULL DEFAULT 42 CHECK (week_hours > 0),
            day_hours_5        numeric(4, 2) NOT NULL DEFAULT 8.6 CHECK (day_hours_5 > 0),
            day_hours_6        numeric(4, 2) NOT NULL DEFAULT 8 CHECK (day_hours_6 > 0),
            tier1_hours        numeric(4, 2) NOT NULL DEFAULT 2 CHECK (tier1_hours >= 0),
            tier1_percent      integer NOT NULL DEFAULT 125 CHECK (tier1_percent >= 100),
            tier2_percent      integer NOT NULL DEFAULT 150 CHECK (tier2_percent >= 100),
            rest_day_percent   integer NOT NULL DEFAULT 150 CHECK (rest_day_percent >= 100),
            rest_weekday       integer NOT NULL DEFAULT 5 CHECK (rest_weekday BETWEEN 0 AND 6),
            updated_at         timestamptz NOT NULL DEFAULT now()
        )
    """)
    for table in ("time_clock_entries", "time_clock_approvals", "time_clock_rules"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.time_clock_rules")
    op.execute("DROP TABLE app.time_clock_approvals")
    op.execute("DROP TABLE app.time_clock_entries")
