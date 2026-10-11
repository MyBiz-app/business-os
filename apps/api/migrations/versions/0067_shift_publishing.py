"""Publishing the shifts roster.

Managers plan shifts as a draft; the team sees a shift only once it is published. Every shift
that exists now counts as published. The business chooses how often the roster goes out (daily,
weekly or monthly), on which weekday or day of the month and at what local time; the default is
every Sunday at 08:00. A background job publishes on schedule, and managers can publish at once.

Revision ID: 0067
Revises: 0066
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    "shifts_publish_auto",
    "shifts_publish_cadence",
    "shifts_publish_weekday",
    "shifts_publish_day",
    "shifts_publish_time",
)


def upgrade() -> None:
    op.execute("ALTER TABLE app.shifts ADD COLUMN published_at timestamptz")
    op.execute("UPDATE app.shifts SET published_at = now()")
    op.execute(
        "CREATE INDEX shifts_unpublished ON app.shifts (tenant_id, starts_at)"
        " WHERE published_at IS NULL"
    )
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN shifts_publish_auto boolean NOT NULL DEFAULT true,
            ADD COLUMN shifts_publish_cadence text NOT NULL DEFAULT 'weekly'
                CHECK (shifts_publish_cadence IN ('daily', 'weekly', 'monthly')),
            ADD COLUMN shifts_publish_weekday smallint NOT NULL DEFAULT 6
                CHECK (shifts_publish_weekday BETWEEN 0 AND 6),  -- 0 = Monday, 6 = Sunday
            ADD COLUMN shifts_publish_day smallint NOT NULL DEFAULT 1
                CHECK (shifts_publish_day BETWEEN 1 AND 28),
            ADD COLUMN shifts_publish_time time NOT NULL DEFAULT '08:00',
            ADD COLUMN shifts_last_auto_published_at timestamptz
    """)
    # The job runs with the owner connection; the API may only change the settings.
    op.execute(f"GRANT UPDATE ({', '.join(COLUMNS)}) ON app.tenants TO app_api")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN shifts_last_auto_published_at, DROP COLUMN shifts_publish_time,
            DROP COLUMN shifts_publish_day, DROP COLUMN shifts_publish_weekday,
            DROP COLUMN shifts_publish_cadence, DROP COLUMN shifts_publish_auto
    """)
    op.execute("DROP INDEX app.shifts_unpublished")
    op.execute("ALTER TABLE app.shifts DROP COLUMN published_at")
