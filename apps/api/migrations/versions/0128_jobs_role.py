"""A role with only the rights background jobs need (go-live completion).

Expand step: the jobs used to run as the database owner, which can also change the schema, switch
row-level security off and drop tables. `app_jobs` can read and write the rows of every business
(background jobs work across businesses, so it bypasses row-level security, like the owner did)
but cannot create, alter or drop anything, truncate a table, or add triggers. The jobs runner
switches to it with SET ROLE (like the API does with `app_api`), so no new password or secret is
needed. Nothing else uses the role, so the previous release keeps working on this database.

Revision ID: 0128
Revises: 0127
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0128"
down_revision: str | None = "0127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_jobs') THEN
                CREATE ROLE app_jobs NOLOGIN BYPASSRLS;
            END IF;
        END
        $$;
    """)
    op.execute("GRANT app_jobs TO CURRENT_USER")
    op.execute("GRANT USAGE ON SCHEMA app TO app_jobs")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO app_jobs")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO app_jobs")
    # Tables and sequences added by later migrations get the same rights.
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA app
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_jobs
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO app_jobs
    """)


def downgrade() -> None:
    # contract: only the downgrade revokes rights, from a role no earlier release uses
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE ALL ON TABLES FROM app_jobs")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE ALL ON SEQUENCES FROM app_jobs")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA app FROM app_jobs")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA app FROM app_jobs")
    op.execute("REVOKE USAGE ON SCHEMA app FROM app_jobs")
    # The role itself stays (roles belong to the whole server, like `app_api`).
