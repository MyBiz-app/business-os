"""The AI agents team (round 5, A1).

An agent is a persona (name, picture, colour, role) with instructions, a toolbox (tool domains),
a branch scope, the roles that may use it and a model tier. The built-in agents live in code
(`app/ai/agents.py`); a row here for a built-in agent only holds the business's overrides, and is
created the first time the owner changes something. Custom agents are full rows.

Conversations remember which agent they are with, the branches they were opened for and the
screen they were opened from.

Revision ID: 0083
Revises: 0082
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0083"
down_revision: str | None = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.ai_agents (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id          uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            -- Null for a custom agent. For a built-in agent the nullable columns below are
            -- overrides: null means "the catalog's default".
            builtin_key        text,
            name               text,
            role_title         text,
            avatar_kind        text CHECK (avatar_kind IN ('preset', 'upload')),
            avatar_preset      text,
            avatar_key         text,
            color              text CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
            topic              text,
            instructions       text CHECK (char_length(instructions) <= 4000),
            tone               text CHECK (tone IN ('friendly', 'formal', 'short')),
            tool_domains       text[],
            enabled            boolean NOT NULL DEFAULT true,
            location_scope     text NOT NULL DEFAULT 'all'
                               CHECK (location_scope IN ('all', 'groups', 'locations')),
            location_ids       uuid[] NOT NULL DEFAULT '{}',
            location_group_ids uuid[] NOT NULL DEFAULT '{}',
            allowed_roles      text[],
            model_tier         text CHECK (model_tier IN ('fast', 'standard', 'strong')),
            created_by         uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at         timestamptz NOT NULL DEFAULT now(),
            updated_at         timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, builtin_key),
            CHECK (builtin_key IS NOT NULL OR (name IS NOT NULL AND tool_domains IS NOT NULL
                                               AND allowed_roles IS NOT NULL))
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_agents TO app_api")
    op.execute("ALTER TABLE app.ai_agents ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ai_agents_tenant ON app.ai_agents TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        ALTER TABLE app.ai_conversations
            ADD COLUMN agent_id         uuid,
            ADD COLUMN agent_key        text NOT NULL DEFAULT 'chief',
            ADD COLUMN title            text,
            -- The branches the user narrowed this chat to (null: no narrowing).
            ADD COLUMN scope            jsonb,
            ADD COLUMN archived_at      timestamptz,
            -- The screen the chat was opened from (e.g. "/schedule").
            ADD COLUMN page_context     text,
            -- A short summary carried over when the user was handed to another agent.
            ADD COLUMN handoff_summary  text,
            ADD FOREIGN KEY (tenant_id, agent_id) REFERENCES app.ai_agents (tenant_id, id)
                ON DELETE SET NULL (agent_id)
    """)
    op.execute(
        "CREATE INDEX ai_conversations_agent_idx ON app.ai_conversations "
        "(tenant_id, user_id, agent_key, updated_at DESC) WHERE archived_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ai_conversations_agent_fk ON app.ai_conversations (tenant_id, agent_id)"
    )
    # Archiving a chat is an update, so the existing grant is enough.


def downgrade() -> None:
    op.execute("DROP INDEX app.ai_conversations_agent_fk")
    op.execute("DROP INDEX app.ai_conversations_agent_idx")
    op.execute("""
        ALTER TABLE app.ai_conversations
            DROP COLUMN handoff_summary, DROP COLUMN page_context, DROP COLUMN archived_at,
            DROP COLUMN scope, DROP COLUMN title, DROP COLUMN agent_key, DROP COLUMN agent_id
    """)
    op.execute("DROP TABLE app.ai_agents")
