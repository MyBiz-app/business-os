"""Saved AI reports and the web search switch (slice C4).

`platform_ai_reports` keeps the reports console agents write (the market researcher now, the
security agent later): a title, a short summary and the full body as JSON. `platform_ai_settings`
gets the web search switch, off, with a number of searches allowed per calendar month (web search
costs money). Searches are counted per conversation. Like the other console AI tables, the report
table is not reachable from the API role: only SECURITY DEFINER functions touch it, and they
check the console permission of the report's kind. This only adds; nothing is changed or dropped.

Revision ID: 0147
Revises: 0146
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0147"
down_revision: str | None = "0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "platform_ai_web_search_get()",
    "platform_ai_web_search_set(boolean, integer)",
    "platform_ai_report_add(text, text, text, jsonb)",
    "platform_ai_reports(text, integer)",
    "platform_ai_report_get(uuid)",
)
# The console permission needed to write or read a kind of report.
KIND_PERMISSION = "CASE p_kind WHEN 'market' THEN 'usage.read' ELSE 'incidents.manage' END"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.platform_ai_settings
            ADD COLUMN web_search_enabled boolean NOT NULL DEFAULT false,
            ADD COLUMN web_search_monthly_limit integer NOT NULL DEFAULT 0
                CHECK (web_search_monthly_limit BETWEEN 0 AND 1000)
    """)
    op.execute("""
        ALTER TABLE app.platform_ai_conversations
            ADD COLUMN web_searches integer NOT NULL DEFAULT 0
    """)
    op.execute("""
        CREATE TABLE app.platform_ai_reports (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            kind       text NOT NULL CHECK (kind IN ('market', 'security')),
            title      text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
            summary    text NOT NULL CHECK (length(summary) BETWEEN 1 AND 2000),
            body       jsonb NOT NULL DEFAULT '{}',
            created_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX platform_ai_reports_kind ON app.platform_ai_reports (kind, created_at DESC)"
    )
    op.execute("ALTER TABLE app.platform_ai_reports ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON app.platform_ai_reports FROM app_api")

    op.execute("""
        CREATE FUNCTION app.platform_ai_web_search_get()
        RETURNS TABLE (enabled boolean, monthly_limit integer, used_this_month integer)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT coalesce(s.web_search_enabled, false),
                   coalesce(s.web_search_monthly_limit, 0),
                   (SELECT coalesce(sum(c.web_searches), 0)::integer
                    FROM app.platform_ai_conversations c
                    WHERE c.updated_at >= date_trunc('month', now()))
            FROM (SELECT 1) one LEFT JOIN app.platform_ai_settings s ON true;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_web_search_set(p_enabled boolean, p_limit integer)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_ai_settings
                (singleton, web_search_enabled, web_search_monthly_limit, updated_by)
            VALUES (true, p_enabled, p_limit, v_email)
            ON CONFLICT (singleton) DO UPDATE
            SET web_search_enabled = excluded.web_search_enabled,
                web_search_monthly_limit = excluded.web_search_monthly_limit,
                updated_by = excluded.updated_by, updated_at = now();
            PERFORM app.platform_audit_add(
                'ai.web_search', NULL,
                jsonb_build_object('enabled', p_enabled, 'monthly_limit', p_limit));
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_ai_report_add(
            p_kind text, p_title text, p_summary text, p_body jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can({KIND_PERMISSION}) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_ai_reports (kind, title, summary, body, created_by)
            VALUES (p_kind, p_title, p_summary, p_body, (SELECT email FROM app.platform_me()))
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_ai_reports(p_kind text, p_limit integer)
        RETURNS TABLE (id uuid, kind text, title text, summary text, created_by text,
                       created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can({KIND_PERMISSION}) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.kind, r.title, r.summary, r.created_by, r.created_at
            FROM app.platform_ai_reports r WHERE r.kind = p_kind
            ORDER BY r.created_at DESC LIMIT least(greatest(p_limit, 1), 100);
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_report_get(p_id uuid)
        RETURNS TABLE (id uuid, kind text, title text, summary text, body jsonb,
                       created_by text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_kind text := (SELECT r.kind FROM app.platform_ai_reports r WHERE r.id = p_id);
        BEGIN
            IF v_kind IS NULL THEN
                RETURN;
            END IF;
            IF NOT app.platform_can(
                CASE v_kind WHEN 'market' THEN 'usage.read' ELSE 'incidents.manage' END) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.kind, r.title, r.summary, r.body, r.created_by, r.created_at
            FROM app.platform_ai_reports r WHERE r.id = p_id;
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops what was added; the previous release never reads any of it.
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.platform_ai_reports")
    op.execute("ALTER TABLE app.platform_ai_conversations DROP COLUMN web_searches")
    op.execute("""
        ALTER TABLE app.platform_ai_settings
            DROP COLUMN web_search_enabled, DROP COLUMN web_search_monthly_limit
    """)
