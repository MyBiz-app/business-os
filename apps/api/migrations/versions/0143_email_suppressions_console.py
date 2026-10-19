"""The console can list the addresses that bounced or complained (K3).

`email_suppressions` has no direct grants, so the console reads it through one function that
checks the `usage.read` permission and returns the last 12 months, newest first, capped at 500.

Revision ID: 0143
Revises: 0142
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0143"
down_revision: str | None = "0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.platform_email_suppressions()
        RETURNS TABLE (address text, reason text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT s.address, s.reason, s.created_at FROM app.email_suppressions s
            WHERE s.created_at > now() - interval '12 months'
            ORDER BY s.created_at DESC LIMIT 500;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_email_suppressions() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_email_suppressions() TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops the function, and the previous release never calls it.
    op.execute("DROP FUNCTION app.platform_email_suppressions()")
