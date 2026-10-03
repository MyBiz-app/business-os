"""AI assistant: conversations, pending actions, audit log and usage events.

The assistant acts only through tools that run with the requesting user's permissions.
Sensitive tools never act directly: they store a pending action (payload + hash + expiry)
that a person confirms; the server re-validates and executes it once, and records it in the
audit log. Every model call records usage (`usage_events`, meter `ai_credits`).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.ai_conversations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            -- The model-facing transcript, append-only (Messages API format).
            messages    jsonb NOT NULL DEFAULT '[]',
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    op.execute(
        "CREATE INDEX ai_conversations_user_idx ON app.ai_conversations "
        "(tenant_id, user_id, updated_at DESC)"
    )
    op.execute("""
        CREATE TABLE app.pending_actions (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            conversation_id  uuid,
            requested_by     uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            agent_key        text NOT NULL,
            tool_name        text NOT NULL,
            payload          jsonb NOT NULL,
            payload_hash     text NOT NULL,
            preview          jsonb NOT NULL,
            risk_level       text NOT NULL CHECK (risk_level IN ('low', 'sensitive')),
            status           text NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'rejected', 'expired', 'executed',
                                               'failed')),
            expires_at       timestamptz NOT NULL,
            decided_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            decided_at       timestamptz,
            result           jsonb,
            created_at       timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, conversation_id) REFERENCES app.ai_conversations (tenant_id, id)
                ON DELETE SET NULL (conversation_id)
        )
    """)
    op.execute("""
        CREATE TABLE app.audit_log (
            id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            actor_type   text NOT NULL CHECK (actor_type IN ('user', 'ai', 'system', 'platform')),
            actor_id     uuid,
            on_behalf_of uuid,
            action       text NOT NULL,
            entity_type  text,
            entity_id    uuid,
            details      jsonb NOT NULL DEFAULT '{}',
            occurred_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX audit_log_tenant_idx ON app.audit_log (tenant_id, occurred_at DESC)")
    op.execute("""
        CREATE TABLE app.usage_events (
            id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            meter        text NOT NULL,
            quantity     numeric(14, 4) NOT NULL CHECK (quantity >= 0),
            details      jsonb NOT NULL DEFAULT '{}',
            source_ref   text,
            occurred_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX usage_events_tenant_idx ON app.usage_events (tenant_id, meter, occurred_at)"
    )

    # Conversations are private to their user within the business.
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.ai_conversations TO app_api")
    op.execute("ALTER TABLE app.ai_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ai_conversations_own ON app.ai_conversations TO app_api
        USING (tenant_id = app.current_tenant_id() AND user_id = app.current_user_id())
        WITH CHECK (tenant_id = app.current_tenant_id() AND user_id = app.current_user_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.pending_actions TO app_api")
    op.execute("ALTER TABLE app.pending_actions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pending_actions_tenant ON app.pending_actions TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Append-only for the API: it can write and read, never change or delete.
    for table in ("audit_log", "usage_events"):
        op.execute(f"GRANT SELECT, INSERT ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute(
        "DROP TABLE app.usage_events, app.audit_log, app.pending_actions, app.ai_conversations"
    )
