"""Client experience API: weekly class-schedule release, profile status, instructor pictures.

A business decides how far ahead clients can book classes: a rolling number of days
(`booking_horizon_days`, default 7), or a weekly release (`weekly_release_weekday` +
`weekly_release_time`: every Thursday 20:00 the next week opens). The team can also publish the
next week early (`schedule_published_until`). A person gets a short free-text status
(`users.status_text`). Clients cannot read `app.users`, so the instructor of a class (name and
picture) reaches them only through two SECURITY DEFINER functions limited to the client's own
business.

Revision ID: 0080
Revises: 0079
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0080"
down_revision: str | None = "0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_COLUMNS = (
    "booking_horizon_days",
    "weekly_release_weekday",
    "weekly_release_time",
    "schedule_published_until",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN booking_horizon_days smallint NOT NULL DEFAULT 7
                CHECK (booking_horizon_days BETWEEN 1 AND 60),
            ADD COLUMN weekly_release_weekday smallint
                CHECK (weekly_release_weekday BETWEEN 0 AND 6),  -- 0 = Monday, 6 = Sunday
            ADD COLUMN weekly_release_time time,
            ADD COLUMN schedule_published_until date,
            ADD CONSTRAINT weekly_release_complete
                CHECK ((weekly_release_weekday IS NULL) = (weekly_release_time IS NULL))
    """)
    op.execute(f"GRANT UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants TO app_api")
    op.execute("""
        ALTER TABLE app.users
            ADD COLUMN status_text text CHECK (char_length(status_text) BETWEEN 1 AND 80)
    """)
    op.execute("""
        CREATE FUNCTION app.client_instructor(p_user_id uuid)
        RETURNS TABLE (id uuid, full_name text, avatar_updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT u.id, u.full_name, u.avatar_updated_at
            FROM app.users u
            JOIN app.tenant_members m ON m.user_id = u.id
            WHERE u.id = p_user_id AND m.tenant_id = app.client_tenant_id()
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.client_instructor_avatar(p_user_id uuid)
        RETURNS TABLE (avatar bytea, content_type text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT u.avatar, u.avatar_content_type
            FROM app.users u
            JOIN app.tenant_members m ON m.user_id = u.id
            WHERE u.id = p_user_id AND u.avatar IS NOT NULL
              AND m.tenant_id = app.client_tenant_id()
        $$
    """)
    for function in ("app.client_instructor(uuid)", "app.client_instructor_avatar(uuid)"):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.client_instructor_avatar(uuid)")
    op.execute("DROP FUNCTION app.client_instructor(uuid)")
    op.execute("ALTER TABLE app.users DROP COLUMN status_text")
    op.execute(f"REVOKE UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("""
        ALTER TABLE app.tenants
            DROP CONSTRAINT weekly_release_complete,
            DROP COLUMN schedule_published_until, DROP COLUMN weekly_release_time,
            DROP COLUMN weekly_release_weekday, DROP COLUMN booking_horizon_days
    """)
