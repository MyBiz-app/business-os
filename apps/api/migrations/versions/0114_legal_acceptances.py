"""Legal document acceptances (go-live, GL10).

One row per person, document and version they accepted: when, from where (address and device) and
in which situation (signing up a business, joining a business as a client, or accepting again
after a document changed). `business_id` only says which business the acceptance happened for; the
row belongs to the person, so it is not tenant-scoped.

Revision ID: 0114
Revises: 0113
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0114"
down_revision: str | None = "0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.legal_acceptances (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            business_id uuid REFERENCES app.tenants (id) ON DELETE SET NULL,
            document    text NOT NULL CHECK (document IN ('terms', 'privacy', 'dpa')),
            version     text NOT NULL,
            context     text NOT NULL CHECK (context IN ('signup', 'client_join', 'reaccept')),
            accepted_at timestamptz NOT NULL DEFAULT now(),
            ip_address  text NOT NULL DEFAULT '',
            user_agent  text NOT NULL DEFAULT ''
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX legal_acceptances_once
            ON app.legal_acceptances (
                user_id, document, version,
                coalesce(business_id, '00000000-0000-0000-0000-000000000000'::uuid)
            )
    """)
    op.execute("CREATE INDEX legal_acceptances_business ON app.legal_acceptances (business_id)")
    # Rows are only added: an acceptance is a record, never edited or removed by the API.
    op.execute("GRANT SELECT, INSERT ON app.legal_acceptances TO app_api")
    op.execute("ALTER TABLE app.legal_acceptances ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY legal_acceptances_self ON app.legal_acceptances TO app_api
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.legal_acceptances")
