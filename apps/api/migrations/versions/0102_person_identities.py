"""ID numbers of the people a business works with (round 6, K1).

`person_identities` is a table of its own, per business, so each business is the keeper of the
data it collected and the number never sits in the wide people tables:
- `id_number_encrypted` holds the number encrypted with the platform secrets key;
- `id_hash` is a keyed hash (per business) that finds the same number twice inside one business
  of the same kind (two employees, two clients) without decrypting anything;
- `id_last4` is what screens show; the full number is revealed only on request, by someone with
  `identity.read`, and every reveal is written to the audit log.
A row belongs to a team member (`user_id`) or to a client (`client_id`), never both. A client
reads and writes only their own row. Businesses decide whether to ask their clients at all
(`tenants.client_id_number`, off by default).

Revision ID: 0102
Revises: 0101
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0102"
down_revision: str | None = "0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants ADD COLUMN client_id_number text NOT NULL DEFAULT 'off'
            CHECK (client_id_number IN ('off', 'optional', 'required'))
    """)
    op.execute("GRANT UPDATE (client_id_number) ON app.tenants TO app_api")
    op.execute("""
        CREATE TABLE app.person_identities (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id             uuid REFERENCES app.users (id) ON DELETE CASCADE,
            client_id           uuid REFERENCES app.clients (id) ON DELETE CASCADE,
            id_type             text NOT NULL CHECK (id_type IN ('il_id', 'passport', 'foreign')),
            country             text NOT NULL CHECK (country ~ '^[A-Z]{2}$'),
            id_number_encrypted bytea NOT NULL,
            id_hash             text NOT NULL,
            id_last4            text NOT NULL CHECK (length(id_last4) BETWEEN 1 AND 4),
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now(),
            CHECK ((user_id IS NOT NULL) <> (client_id IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX person_identities_user ON app.person_identities (tenant_id, user_id)"
        " WHERE user_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX person_identities_client"
        " ON app.person_identities (tenant_id, client_id) WHERE client_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX person_identities_user_hash"
        " ON app.person_identities (tenant_id, id_hash) WHERE user_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX person_identities_client_hash"
        " ON app.person_identities (tenant_id, id_hash) WHERE client_id IS NOT NULL"
    )
    op.execute("CREATE INDEX person_identities_client_fk ON app.person_identities (client_id)")
    op.execute("CREATE INDEX person_identities_user_fk ON app.person_identities (user_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.person_identities TO app_api")
    op.execute("ALTER TABLE app.person_identities ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY person_identities_tenant ON app.person_identities TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY person_identities_client ON app.person_identities TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)
    # A client adding or revealing their own number leaves a trace in the business's audit log.
    op.execute("""
        CREATE POLICY audit_log_client_identity ON app.audit_log FOR INSERT TO app_api
        WITH CHECK (tenant_id = app.client_tenant_id() AND actor_type = 'user'
                    AND actor_id = app.current_user_id() AND action LIKE 'identity.%')
    """)


def downgrade() -> None:
    op.execute("DROP POLICY audit_log_client_identity ON app.audit_log")
    op.execute("DROP TABLE app.person_identities")
    op.execute("ALTER TABLE app.tenants DROP COLUMN client_id_number")
