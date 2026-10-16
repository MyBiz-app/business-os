"""Scheduled tasks for AI agents (round 5, A10).

A task is something an agent does later, once or on a repeat: an `action` (a write tool the user
approved on a card, run at the set time after the server checks everything again) or an
`agent_run` (an instruction the agent follows, read-only unless the user approves what it
proposes). Every run is recorded in `ai_task_runs`.

Revision ID: 0092
Revises: 0087
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0092"
down_revision: str | None = "0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.ai_scheduled_tasks (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            created_by    uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            agent_key     text NOT NULL,
            kind          text NOT NULL CHECK (kind IN ('action', 'agent_run')),
            title         text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
            -- kind 'action': the write tool, its approved payload and the payload's hash.
            tool_name     text,
            payload       jsonb,
            payload_hash  text,
            preview       jsonb,
            -- kind 'agent_run': what the agent is told to do.
            instruction   text CHECK (char_length(instruction) <= 2000),
            -- {"type": "once|daily|weekly|monthly", "date", "time", "weekdays", "day"}, local time.
            schedule      jsonb NOT NULL,
            time_zone     text NOT NULL,
            next_run_at   timestamptz,
            last_run_at   timestamptz,
            status        text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'paused', 'done', 'failed')),
            -- Why a task was paused or failed by the system (e.g. member_gone).
            status_reason text,
            failures      integer NOT NULL DEFAULT 0,
            max_credits   integer NOT NULL DEFAULT 20 CHECK (max_credits > 0),
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'action' AND tool_name IS NOT NULL AND payload IS NOT NULL
                    AND payload_hash IS NOT NULL)
                   OR (kind = 'agent_run' AND instruction IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE INDEX ai_scheduled_tasks_due_idx ON app.ai_scheduled_tasks (next_run_at) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX ai_scheduled_tasks_owner_idx ON app.ai_scheduled_tasks "
        "(tenant_id, created_by, status)"
    )
    op.execute("""
        CREATE TABLE app.ai_task_runs (
            id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id          uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            task_id            uuid NOT NULL,
            started_at         timestamptz NOT NULL DEFAULT now(),
            finished_at        timestamptz,
            status             text NOT NULL DEFAULT 'running'
                               CHECK (status IN ('running', 'ok', 'failed', 'skipped')),
            credits            numeric(14, 4) NOT NULL DEFAULT 0,
            result             jsonb,
            conversation_id    uuid,
            pending_action_ids uuid[] NOT NULL DEFAULT '{}',
            FOREIGN KEY (tenant_id, task_id) REFERENCES app.ai_scheduled_tasks (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX ai_task_runs_task_idx ON app.ai_task_runs "
        "(tenant_id, task_id, started_at DESC)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_scheduled_tasks TO app_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.ai_task_runs TO app_api")
    for table in ("ai_scheduled_tasks", "ai_task_runs"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.ai_task_runs")
    op.execute("DROP TABLE app.ai_scheduled_tasks")
