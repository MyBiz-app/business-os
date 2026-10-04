"""Health declarations: clients answer the business's health questions and sign them.

The questions come from the vertical pack (app/health.py); each declaration stores the exact
questions and answers it was signed with. A declaration with any "yes" needs review by the
business before the client can book in the app. Declarations are valid for one year.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
        ADD COLUMN requires_health_declaration boolean NOT NULL DEFAULT false
    """)
    op.execute("""
        CREATE TABLE app.health_declarations (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id     uuid NOT NULL,
            form_key      text NOT NULL,
            locale        text NOT NULL CHECK (locale IN ('he', 'en')),
            answers       jsonb NOT NULL,
            statement     text NOT NULL,
            all_clear     boolean NOT NULL,
            signed_name   text NOT NULL CHECK (length(trim(signed_name)) > 1),
            signed_by     uuid REFERENCES app.users (id) ON DELETE SET NULL,
            signed_at     timestamptz NOT NULL DEFAULT now(),
            valid_until   date NOT NULL,
            status        text NOT NULL CHECK (status IN ('valid', 'needs_review', 'approved',
                                                          'rejected')),
            reviewed_by   uuid REFERENCES app.users (id) ON DELETE SET NULL,
            reviewed_at   timestamptz,
            review_note   text,
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX health_declarations_client_idx "
        "ON app.health_declarations (tenant_id, client_id, signed_at DESC)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.health_declarations TO app_api")
    op.execute("ALTER TABLE app.health_declarations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY health_declarations_tenant ON app.health_declarations TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Clients read and sign their own; they cannot change one after signing.
    op.execute("""
        CREATE POLICY health_declarations_client_select ON app.health_declarations
        FOR SELECT TO app_api USING (client_id = app.current_client_id())
    """)
    op.execute("""
        CREATE POLICY health_declarations_client_insert ON app.health_declarations
        FOR INSERT TO app_api
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.health_declarations")
    op.execute("ALTER TABLE app.tenants DROP COLUMN requires_health_declaration")
