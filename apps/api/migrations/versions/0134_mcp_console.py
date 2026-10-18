"""AI connectors in the MyBiz console (round 7, R37b): who uses them.

Expand step only: one new read-only function. For every business with an AI connection it gives
the number of live connections, the apps, the calls in the window and what became of the changes
the apps proposed. Console staff with the usage permission only.

# contract: only the downgrade drops the function; nothing else reads it.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0134"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.platform_mcp_usage(p_days integer)
        RETURNS TABLE (tenant_id uuid, name text, connections integer, apps text[],
                       calls bigint, last_call timestamptz, proposed integer, executed integer,
                       rejected integer, waiting integer)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT t.id, t.name,
                   (SELECT count(*)::integer FROM app.mcp_connections c
                    WHERE c.tenant_id = t.id AND c.revoked_at IS NULL
                      AND c.access_hash IS NOT NULL),
                   coalesce((SELECT array_agg(DISTINCT c.client_name ORDER BY c.client_name)
                             FROM app.mcp_connections c
                             WHERE c.tenant_id = t.id AND c.revoked_at IS NULL
                               AND c.access_hash IS NOT NULL), '{}'::text[]),
                   coalesce((SELECT sum(u.quantity)::bigint FROM app.usage_events u
                             WHERE u.tenant_id = t.id AND u.meter = 'mcp_calls'
                               AND u.occurred_at > now() - make_interval(days => p_days)), 0),
                   (SELECT max(u.occurred_at) FROM app.usage_events u
                    WHERE u.tenant_id = t.id AND u.meter = 'mcp_calls'),
                   (SELECT count(*)::integer FROM app.pending_actions a
                    WHERE a.tenant_id = t.id AND a.agent_key = 'mcp'
                      AND a.created_at > now() - make_interval(days => p_days)),
                   (SELECT count(*)::integer FROM app.pending_actions a
                    WHERE a.tenant_id = t.id AND a.agent_key = 'mcp' AND a.status = 'executed'
                      AND a.created_at > now() - make_interval(days => p_days)),
                   (SELECT count(*)::integer FROM app.pending_actions a
                    WHERE a.tenant_id = t.id AND a.agent_key = 'mcp' AND a.status = 'rejected'
                      AND a.created_at > now() - make_interval(days => p_days)),
                   (SELECT count(*)::integer FROM app.pending_actions a
                    WHERE a.tenant_id = t.id AND a.agent_key = 'mcp' AND a.status = 'pending'
                      AND a.expires_at > now())
            FROM app.tenants t
            WHERE EXISTS (SELECT 1 FROM app.mcp_connections c WHERE c.tenant_id = t.id)
            ORDER BY 5 DESC, t.name;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_mcp_usage(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_mcp_usage(integer) TO app_api")


def downgrade() -> None:
    # contract: a rollback of this release drops the function; nothing else reads it
    op.execute("DROP FUNCTION app.platform_mcp_usage(integer)")
