"""Shift templates and coverage rules.

A template is a named shift type of one branch ("Morning 07:00-15:00") applied with one click
when planning. A coverage rule is the least number of people a branch needs on shift on a weekday
between two times (minutes from midnight; 1440 is the end of the day); the shifts board flags the
stretches that fall short.

Revision ID: 0065
Revises: 0064
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("shift_templates", "coverage_rules")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.shift_templates (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id uuid NOT NULL,
            name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
            starts      time NOT NULL,
            ends        time NOT NULL CHECK (ends <> starts),  -- earlier than starts: past midnight
            position    text CHECK (length(position) <= 60),
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, location_id, name),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE app.coverage_rules (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id  uuid NOT NULL,
            weekday      smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
            starts_minute smallint NOT NULL CHECK (starts_minute BETWEEN 0 AND 1439),
            ends_minute  smallint NOT NULL CHECK (ends_minute BETWEEN 1 AND 1440),
            min_staff    smallint NOT NULL CHECK (min_staff BETWEEN 1 AND 50),
            created_at   timestamptz NOT NULL DEFAULT now(),
            CHECK (ends_minute > starts_minute),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX coverage_rules_location ON app.coverage_rules (tenant_id, location_id)"
    )
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.coverage_rules")
    op.execute("DROP TABLE app.shift_templates")
