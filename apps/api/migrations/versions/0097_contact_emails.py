"""Contact emails of a business and of its branches (round 5, F3).

One row per purpose (main, inbox, billing, reply_to, notifications), for the business
(location_id null) or for one branch. A branch without its own row inherits the business's.
A new address is unusable until the link emailed to it is opened (verified_at).

Revision ID: 0097
Revises: 0096
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0097"
down_revision: str | None = "0096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.contact_emails (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id uuid,
            purpose     text NOT NULL
                CHECK (purpose IN ('main', 'inbox', 'billing', 'reply_to', 'notifications')),
            email       text NOT NULL CHECK (length(email) BETWEEN 3 AND 254),
            verified_at timestamptz,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX contact_emails_scope_purpose ON app.contact_emails
            (tenant_id, coalesce(location_id, '00000000-0000-0000-0000-000000000000'), purpose)
    """)
    op.execute(
        "CREATE INDEX contact_emails_location ON app.contact_emails (tenant_id, location_id)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.contact_emails TO app_api")
    op.execute("ALTER TABLE app.contact_emails ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY contact_emails_tenant ON app.contact_emails TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    # A client of the business sees its confirmed main email (the contact details), nothing else.
    op.execute("""
        CREATE POLICY contact_emails_client_main ON app.contact_emails FOR SELECT TO app_api
        USING (tenant_id = app.client_tenant_id() AND purpose = 'main'
               AND verified_at IS NOT NULL)
    """)
    # The confirmation link is opened with no sign-in; the API checks its signature first.
    op.execute("""
        CREATE FUNCTION app.confirm_contact_email(p_tenant uuid, p_id uuid, p_email text)
        RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            WITH done AS (
                UPDATE app.contact_emails SET verified_at = coalesce(verified_at, now())
                WHERE id = p_id AND tenant_id = p_tenant AND email = p_email RETURNING 1
            )
            SELECT EXISTS (SELECT 1 FROM done)
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.confirm_contact_email(uuid, uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.confirm_contact_email(uuid, uuid, text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.confirm_contact_email(uuid, uuid, text)")
    op.execute("DROP TABLE app.contact_emails")
