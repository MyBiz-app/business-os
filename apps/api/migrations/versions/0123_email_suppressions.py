"""Addresses we must not email again (go-live, GL22).

When the email provider reports a hard bounce or a spam complaint, the address goes into
`email_suppressions`. Every send checks it first; the CRM client card shows the flag. The table
has no direct grants: the signed webhook files entries through `app.suppress_email()` and the
senders and the CRM read through `app.email_is_suppressed()`.

Revision ID: 0123
Revises: 0122
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0123"
down_revision: str | None = "0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.email_suppressions (
            address       text PRIMARY KEY CHECK (address = lower(address)),
            reason        text NOT NULL CHECK (reason IN ('bounced', 'complained')),
            provider_ref  text,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE app.email_suppressions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE FUNCTION app.suppress_email(p_address text, p_reason text, p_ref text)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            INSERT INTO app.email_suppressions (address, reason, provider_ref)
            VALUES (lower(trim(p_address)), p_reason, p_ref)
            ON CONFLICT (address) DO NOTHING
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.email_is_suppressed(p_address text)
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT EXISTS (SELECT 1 FROM app.email_suppressions
                           WHERE address = lower(trim(p_address)))
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.suppress_email(text, text, text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app.email_is_suppressed(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.suppress_email(text, text, text) TO app_api")
    op.execute("GRANT EXECUTE ON FUNCTION app.email_is_suppressed(text) TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops these, and the previous release never reads them.
    op.execute("DROP FUNCTION app.email_is_suppressed(text)")
    op.execute("DROP FUNCTION app.suppress_email(text, text, text)")
    op.execute("DROP TABLE app.email_suppressions")
