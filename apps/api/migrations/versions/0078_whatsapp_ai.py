"""AI replies on WhatsApp (module `whatsapp_ai`): conversations, the inbox and booking offers.

A client's WhatsApp message reaches the business's messaging provider, which calls our webhook;
`app.receive_whatsapp` files it in the inbox (only while the business has the module), and the
answer-whatsapp job answers it with the AI, which may only use the client-facing tools in
`app/messaging/whatsapp_ai.py`. The AI never books: offering a free slot stores a booking offer
(payload + hash + expiry). The client accepts it by replying 1 (or with the provider's button);
the server, not the model, re-checks and books it once.

A conversation marked `test` is the business trying the bot from its settings: the same flow,
but nothing is sent and an accepted offer books nothing.

Revision ID: 0078
Revises: 0077
Create Date: 2026-10-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0078"
down_revision: str | None = "0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_table(table: str, grants: str) -> None:
    op.execute(f"GRANT {grants} ON app.{table} TO app_api")
    op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table}_tenant ON app.{table} TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.whatsapp_conversations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            phone       text NOT NULL CHECK (length(phone) BETWEEN 3 AND 30),
            -- Digits only, Israeli +972 written as 0 (app.catalog.importing.phone_key).
            phone_key   text NOT NULL,
            client_id   uuid,
            test        boolean NOT NULL DEFAULT false,
            -- The model-facing transcript, append-only (Messages API format).
            messages    jsonb NOT NULL DEFAULT '[]',
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, phone_key, test),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX whatsapp_conversations_recent ON app.whatsapp_conversations "
        "(tenant_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX whatsapp_conversations_client ON app.whatsapp_conversations "
        "(tenant_id, client_id)"
    )
    _tenant_table("whatsapp_conversations", "SELECT, INSERT, UPDATE, DELETE")

    op.execute("""
        CREATE TABLE app.whatsapp_offers (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            conversation_id  uuid NOT NULL,
            client_id        uuid NOT NULL,
            kind             text NOT NULL CHECK (kind IN ('book_session')),
            payload          jsonb NOT NULL,
            payload_hash     text NOT NULL,
            preview          jsonb NOT NULL,
            status           text NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'accepted', 'declined', 'expired',
                                               'failed', 'replaced')),
            expires_at       timestamptz NOT NULL,
            decided_at       timestamptz,
            result           jsonb,
            created_at       timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, conversation_id)
                REFERENCES app.whatsapp_conversations (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX whatsapp_offers_conversation ON app.whatsapp_offers "
        "(tenant_id, conversation_id, created_at DESC)"
    )
    op.execute("CREATE INDEX whatsapp_offers_client ON app.whatsapp_offers (tenant_id, client_id)")
    _tenant_table("whatsapp_offers", "SELECT, INSERT, UPDATE")

    # Written by the webhook through app.receive_whatsapp; the job marks each message handled.
    op.execute("""
        CREATE TABLE app.whatsapp_inbox (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            provider      text NOT NULL,
            provider_ref  text NOT NULL,
            from_phone    text NOT NULL CHECK (length(from_phone) BETWEEN 3 AND 30),
            body          text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
            status        text NOT NULL DEFAULT 'received'
                          CHECK (status IN ('received', 'answered', 'skipped', 'failed')),
            note          text,
            attempts      integer NOT NULL DEFAULT 0,
            received_at   timestamptz NOT NULL DEFAULT now(),
            handled_at    timestamptz,
            UNIQUE (tenant_id, provider, provider_ref)
        )
    """)
    op.execute(
        "CREATE INDEX whatsapp_inbox_waiting ON app.whatsapp_inbox (received_at) "
        "WHERE status = 'received'"
    )
    _tenant_table("whatsapp_inbox", "SELECT, UPDATE, DELETE")

    # The webhook has no signed-in user: this files a verified message for one business, and
    # only while it has the module (a provider's retry of the same message is ignored).
    op.execute("""
        CREATE FUNCTION app.receive_whatsapp(
            p_tenant_id uuid, p_provider text, p_ref text, p_from text, p_body text
        ) RETURNS boolean
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            WITH filed AS (
                INSERT INTO app.whatsapp_inbox (tenant_id, provider, provider_ref, from_phone, body)
                SELECT p_tenant_id, p_provider, p_ref, left(p_from, 30), left(p_body, 4000)
                WHERE EXISTS (
                    SELECT 1 FROM app.tenant_modules m JOIN app.tenants t ON t.id = m.tenant_id
                    WHERE m.tenant_id = p_tenant_id AND m.module_key = 'whatsapp_ai'
                      AND t.closed_at IS NULL
                ) AND length(trim(p_body)) > 0
                ON CONFLICT (tenant_id, provider, provider_ref) DO NOTHING
                RETURNING 1
            )
            SELECT EXISTS (SELECT 1 FROM filed)
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app.receive_whatsapp(uuid, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.receive_whatsapp(uuid, text, text, text, text) TO app_api"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION app.receive_whatsapp(uuid, text, text, text, text)")
    op.execute("DROP TABLE app.whatsapp_inbox, app.whatsapp_offers, app.whatsapp_conversations")
