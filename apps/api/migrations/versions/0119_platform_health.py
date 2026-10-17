"""System health for the MyBiz console (go-live, GL13).

`app.platform_health()` gathers what the health page shows and the API role may not read itself:
the latest run of each background job (app.job_runs has no grant), the queues of messages and
notifications still waiting, and the database size. Only the MyBiz team with the usage permission
may call it.

Revision ID: 0119
Revises: 0118
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0119"
down_revision: str | None = "0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.platform_health()
        RETURNS jsonb
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_jobs jsonb;
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            SELECT coalesce(jsonb_agg(row_to_json(j) ORDER BY j.job), '[]'::jsonb) INTO v_jobs
            FROM (
                SELECT r.job,
                       max(r.started_at) AS last_run_at,
                       max(r.finished_at) FILTER (WHERE r.ok) AS last_ok_at,
                       (array_agg(r.ok ORDER BY r.started_at DESC)
                            FILTER (WHERE r.finished_at IS NOT NULL))[1] AS last_ok,
                       (array_agg(r.result ORDER BY r.started_at DESC)
                            FILTER (WHERE r.finished_at IS NOT NULL))[1] AS last_result,
                       count(*) FILTER (WHERE r.started_at > now() - interval '24 hours')
                           AS runs_24h,
                       count(*) FILTER (WHERE r.ok IS FALSE
                                        AND r.started_at > now() - interval '24 hours')
                           AS failures_24h
                FROM app.job_runs r
                WHERE r.started_at > now() - interval '30 days'
                GROUP BY r.job
            ) j;
            RETURN jsonb_build_object(
                'jobs', v_jobs,
                'messages_queued', (SELECT count(*) FROM app.messages WHERE status = 'queued'),
                'messages_failed_24h', (SELECT count(*) FROM app.messages
                                        WHERE status = 'failed'
                                          AND created_at > now() - interval '24 hours'),
                'emails_waiting', (SELECT count(*) FROM app.notifications
                                   WHERE email_status = 'pending'),
                'database_bytes', pg_database_size(current_database())
            );
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_health() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_health() TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_health()")
