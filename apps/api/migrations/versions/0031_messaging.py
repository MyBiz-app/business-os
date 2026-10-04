"""Messaging (WhatsApp / SMS), simulated until a provider is connected: message templates,
broadcasts to a segment ("campaigns") and a per-recipient message log.

Every message is recorded with the exact text sent and counted as usage (meter "messages").
While simulated nothing leaves the system; a provider (WhatsApp Business API / SMS gateway)
will deliver the same rows and update their status.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_table(name: str, grants: str) -> None:
    op.execute(f"GRANT {grants} ON app.{name} TO app_api")
    op.execute(f"ALTER TABLE app.{name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {name}_tenant ON app.{name} TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.message_templates (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
            body        text NOT NULL CHECK (length(body) BETWEEN 1 AND 1000),
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    _tenant_table("message_templates", "SELECT, INSERT, DELETE")

    op.execute("""
        CREATE TABLE app.campaigns (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            audience    text NOT NULL,
            channel     text NOT NULL CHECK (channel IN ('whatsapp', 'sms')),
            body        text NOT NULL CHECK (length(body) BETWEEN 1 AND 1000),
            recipients  integer NOT NULL,
            created_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    _tenant_table("campaigns", "SELECT, INSERT")

    op.execute("""
        CREATE TABLE app.messages (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            campaign_id  uuid,
            client_id    uuid,
            lead_id      uuid,
            channel      text NOT NULL CHECK (channel IN ('whatsapp', 'sms')),
            to_phone     text NOT NULL CHECK (length(to_phone) <= 30),
            body         text NOT NULL CHECK (length(body) BETWEEN 1 AND 1100),
            status       text NOT NULL CHECK (status IN ('queued', 'sent', 'failed')),
            simulated    boolean NOT NULL DEFAULT true,
            created_by   uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            CHECK ((client_id IS NULL) <> (lead_id IS NULL)),
            FOREIGN KEY (tenant_id, campaign_id) REFERENCES app.campaigns (tenant_id, id)
                ON DELETE SET NULL (campaign_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, lead_id) REFERENCES app.leads (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX messages_client ON app.messages (client_id, created_at)")
    op.execute("CREATE INDEX messages_lead ON app.messages (lead_id, created_at)")
    op.execute("CREATE INDEX messages_campaign ON app.messages (campaign_id)")
    _tenant_table("messages", "SELECT, INSERT, DELETE")


def downgrade() -> None:
    op.execute("DROP TABLE app.messages")
    op.execute("DROP TABLE app.campaigns")
    op.execute("DROP TABLE app.message_templates")
