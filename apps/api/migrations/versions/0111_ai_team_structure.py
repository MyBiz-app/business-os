"""AI team structure (round 6, U3).

Who reports to whom, which team an agent belongs to and where it sits on the map. A built-in
agent keeps these on its override row (created the first time the owner changes something), like
its other overrides. A null `reports_to_key` means "reports to the chief" for every agent but the
chief, so a business that never edits the structure behaves as before.

Revision ID: 0111
Revises: 0103
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0111"
down_revision: str | None = "0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.ai_agent_teams (
            id         uuid NOT NULL,
            tenant_id  uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name       text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 60),
            color      text NOT NULL DEFAULT '#6B7280' CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
            -- An agent key (a built-in key or "custom:<id>"): the team's lead, if it has one.
            lead_key   text,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, id)
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_agent_teams TO app_api")
    op.execute("ALTER TABLE app.ai_agent_teams ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ai_agent_teams_tenant ON app.ai_agent_teams TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        ALTER TABLE app.ai_agents
            ADD COLUMN reports_to_key text,
            ADD COLUMN team_id uuid,
            -- Manual position on the map, in percent of the stage (null: automatic layout).
            ADD COLUMN map_x real CHECK (map_x BETWEEN 0 AND 100),
            ADD COLUMN map_y real CHECK (map_y BETWEEN 0 AND 100),
            ADD FOREIGN KEY (tenant_id, team_id) REFERENCES app.ai_agent_teams (tenant_id, id)
                ON DELETE SET NULL (team_id)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE app.ai_agents
            DROP COLUMN map_y, DROP COLUMN map_x, DROP COLUMN team_id, DROP COLUMN reports_to_key
    """)
    op.execute("DROP TABLE app.ai_agent_teams")
