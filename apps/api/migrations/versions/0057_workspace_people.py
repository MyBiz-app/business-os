"""People and structure of a business (workspace upgrade, docs/proposals/crm-upgrade-2026-10.md).

- Personal profiles: a profile picture (kept in the database like the business logo, at most
  512 KB) and a phone number on `app.users`, plus the person's color palette. Pictures are read
  only by the person and by members of a business they belong to (the `users_same_tenant` rule).
- The business's identity: its legal entity type and registration number (ח.פ., עוסק מורשה...),
  and a cover image for its workspace (at most 1.5 MB).
- Organization: a job title and who a member reports to, per business. Reporting never grants
  permissions; a member cannot report to themself or, through others, to someone below them.
- Branch opening hours (`location_hours`): one or more intervals per weekday, so a break is the
  gap between two intervals. Different from staff availability (`staff_hours`) and from shifts.
- Shifts: when a team member works at a branch. Overlapping shifts of one person are refused by
  the API (under a lock), not by a constraint, so no extension is needed.

Revision ID: 0057
Revises: 0056
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_COLUMNS = (
    "legal_entity_type",
    "business_number",
    "cover",
    "cover_content_type",
    "cover_updated_at",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.users
            ADD COLUMN phone text CHECK (length(phone) <= 30),
            ADD COLUMN palette text CHECK (palette IN ('mybiz', 'ocean', 'forest')),
            ADD COLUMN avatar bytea CHECK (octet_length(avatar) <= 524288),
            ADD COLUMN avatar_content_type text
                CHECK (avatar_content_type IN ('image/png', 'image/jpeg', 'image/webp')),
            ADD COLUMN avatar_updated_at timestamptz
    """)

    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN legal_entity_type text CHECK (legal_entity_type IN (
                'company', 'licensed_dealer', 'exempt_dealer', 'nonprofit', 'partnership', 'other'
            )),
            ADD COLUMN business_number text CHECK (business_number ~ '^[0-9A-Za-z-]{2,20}$'),
            ADD COLUMN cover bytea CHECK (octet_length(cover) <= 1572864),
            ADD COLUMN cover_content_type text
                CHECK (cover_content_type IN ('image/png', 'image/jpeg', 'image/webp')),
            ADD COLUMN cover_updated_at timestamptz
    """)
    op.execute(f"GRANT UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants TO app_api")

    op.execute("""
        ALTER TABLE app.tenant_members
            ADD COLUMN job_title text CHECK (length(job_title) <= 80),
            ADD COLUMN reports_to uuid CHECK (reports_to <> user_id),
            ADD CONSTRAINT tenant_members_reports_to_fkey FOREIGN KEY (tenant_id, reports_to)
                REFERENCES app.tenant_members (tenant_id, user_id) ON DELETE SET NULL (reports_to)
    """)
    op.execute(
        "CREATE INDEX tenant_members_reports_to ON app.tenant_members (tenant_id, reports_to)"
    )
    # A reporting line never loops: walk up from the new manager and refuse to meet the member.
    op.execute("""
        CREATE FUNCTION app.check_reporting_line() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            IF NEW.reports_to IS NOT NULL AND EXISTS (
                WITH RECURSIVE up (user_id, depth) AS (
                    SELECT m.reports_to, 1 FROM app.tenant_members m
                    WHERE m.tenant_id = NEW.tenant_id AND m.user_id = NEW.reports_to
                    UNION ALL
                    SELECT m.reports_to, up.depth + 1 FROM app.tenant_members m
                    JOIN up ON m.tenant_id = NEW.tenant_id AND m.user_id = up.user_id
                    WHERE up.depth < 100
                )
                SELECT 1 FROM up WHERE up.user_id = NEW.user_id
            ) THEN
                RAISE EXCEPTION 'reporting cycle' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER tenant_members_reporting_line
        BEFORE INSERT OR UPDATE OF reports_to ON app.tenant_members
        FOR EACH ROW EXECUTE FUNCTION app.check_reporting_line()
    """)

    op.execute("""
        CREATE TABLE app.location_hours (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id uuid NOT NULL,
            weekday     smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
            opens       time NOT NULL,
            closes      time NOT NULL CHECK (closes > opens),
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX location_hours_location ON app.location_hours (tenant_id, location_id)"
    )

    op.execute("""
        CREATE TABLE app.shifts (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id uuid NOT NULL,
            user_id     uuid NOT NULL,
            starts_at   timestamptz NOT NULL,
            ends_at     timestamptz NOT NULL,
            position    text CHECK (length(position) <= 60),
            note        text CHECK (length(note) <= 200),
            created_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CHECK (ends_at > starts_at AND ends_at - starts_at <= interval '24 hours'),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX shifts_time ON app.shifts (tenant_id, starts_at)")
    op.execute("CREATE INDEX shifts_user ON app.shifts (tenant_id, user_id, starts_at)")

    for table in ("location_hours", "shifts"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.shifts")
    op.execute("DROP TABLE app.location_hours")
    op.execute("DROP TRIGGER tenant_members_reporting_line ON app.tenant_members")
    op.execute("DROP FUNCTION app.check_reporting_line()")
    op.execute("DROP INDEX app.tenant_members_reports_to")
    op.execute("""
        ALTER TABLE app.tenant_members
            DROP CONSTRAINT tenant_members_reports_to_fkey,
            DROP COLUMN reports_to, DROP COLUMN job_title
    """)
    op.execute(f"REVOKE UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants FROM app_api")
    op.execute(f"ALTER TABLE app.tenants DROP COLUMN {', DROP COLUMN '.join(TENANT_COLUMNS)}")
    op.execute("""
        ALTER TABLE app.users
            DROP COLUMN phone, DROP COLUMN palette, DROP COLUMN avatar,
            DROP COLUMN avatar_content_type, DROP COLUMN avatar_updated_at
    """)
