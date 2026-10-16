"""Uploaded pictures and drafts for AI agents (round 5, A4).

An agent's face is a gallery preset or a picture the business uploaded. The bytes live in their own
table so loading the team never drags images along; `ai_agents.avatar_key` holds the version of the
upload (it changes with every new picture, which busts browser caches).

A draft agent is one the new-agent wizard is still testing: only those who manage the team can
talk to it, and it is not part of the team until the wizard saves it.

Revision ID: 0094
Revises: 0087
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0094"
down_revision: str | None = "0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.ai_agents ADD COLUMN draft boolean NOT NULL DEFAULT false")
    op.execute("""
        CREATE TABLE app.ai_agent_avatars (
            tenant_id    uuid NOT NULL,
            agent_id     uuid NOT NULL,
            content      bytea NOT NULL,
            content_type text NOT NULL,
            updated_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, agent_id),
            FOREIGN KEY (tenant_id, agent_id) REFERENCES app.ai_agents (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_agent_avatars TO app_api")
    op.execute("ALTER TABLE app.ai_agent_avatars ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ai_agent_avatars_tenant ON app.ai_agent_avatars TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app.ai_agents DROP COLUMN draft")
    op.execute("DROP TABLE app.ai_agent_avatars")
