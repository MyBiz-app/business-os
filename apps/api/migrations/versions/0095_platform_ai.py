"""AI in the MyBiz console (round 5, A9): platform-wide AI settings (model per tier, emergency
stop), per-business AI pauses, the console assistant's conversations, and the cost board.

The settings and pauses are not reachable from the API: only SECURITY DEFINER functions touch
them, and those check the console permission. Businesses learn only whether AI is paused for
them (`ai_platform_state`). Console conversations are private to the team member who started
them.

Revision ID: 0095
Revises: 0094
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0095"
down_revision: str | None = "0094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "ai_platform_state()",
    "platform_ai_settings_get()",
    "platform_ai_settings_set(boolean, text, text, text)",
    "platform_ai_pauses()",
    "platform_ai_pause(uuid, boolean, text)",
    "platform_ai_costs(integer)",
    "platform_ai_audit(text, uuid, jsonb)",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.platform_ai_settings (
            singleton      boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            kill_all       boolean NOT NULL DEFAULT false,
            -- A model id from the registry to serve a tier; null: the deployment's default.
            model_fast     text,
            model_standard text,
            model_strong   text,
            updated_by     text,
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.platform_ai_pauses (
            tenant_id uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            reason    text NOT NULL CHECK (length(reason) BETWEEN 3 AND 500),
            paused_by text NOT NULL,
            paused_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.platform_ai_conversations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            staff_email text NOT NULL,
            role        text NOT NULL CHECK (role IN
                        ('manager', 'support', 'health', 'billing', 'growth')),
            title       text,
            messages    jsonb NOT NULL DEFAULT '[]',
            credits     numeric NOT NULL DEFAULT 0,  -- model cost so far, in AI credits
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX platform_ai_conversations_staff "
        "ON app.platform_ai_conversations (staff_email, updated_at DESC)"
    )
    for table in ("platform_ai_settings", "platform_ai_pauses"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON app.{table} FROM app_api")
    op.execute("ALTER TABLE app.platform_ai_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.platform_ai_conversations TO app_api
    """)
    op.execute("""
        CREATE POLICY platform_ai_conversations_own ON app.platform_ai_conversations
        TO app_api
        USING (app.is_platform_admin()
               AND staff_email = (SELECT m.email FROM app.platform_me() m))
        WITH CHECK (app.is_platform_admin()
                    AND staff_email = (SELECT m.email FROM app.platform_me() m))
    """)

    # What a business's own session may learn: is AI stopped for it, and which models to use.
    op.execute("""
        CREATE FUNCTION app.ai_platform_state()
        RETURNS TABLE (paused boolean, model_fast text, model_standard text, model_strong text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT coalesce(s.kill_all, false) OR EXISTS (
                       SELECT 1 FROM app.platform_ai_pauses p
                       WHERE p.tenant_id = app.current_tenant_id()),
                   s.model_fast, s.model_standard, s.model_strong
            FROM (SELECT 1) one LEFT JOIN app.platform_ai_settings s ON true
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_settings_get()
        RETURNS TABLE (kill_all boolean, model_fast text, model_standard text,
                       model_strong text, updated_by text, updated_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT coalesce(s.kill_all, false), s.model_fast, s.model_standard,
                   s.model_strong, s.updated_by, s.updated_at
            FROM (SELECT 1) one LEFT JOIN app.platform_ai_settings s ON true;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_settings_set(
            p_kill_all boolean, p_fast text, p_standard text, p_strong text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_ai_settings
                (singleton, kill_all, model_fast, model_standard, model_strong, updated_by)
            VALUES (true, p_kill_all, p_fast, p_standard, p_strong, v_email)
            ON CONFLICT (singleton) DO UPDATE
            SET kill_all = excluded.kill_all, model_fast = excluded.model_fast,
                model_standard = excluded.model_standard, model_strong = excluded.model_strong,
                updated_by = excluded.updated_by, updated_at = now();
            PERFORM app.platform_audit_add(
                'ai.settings', NULL,
                jsonb_build_object('kill_all', p_kill_all, 'model_fast', p_fast,
                                   'model_standard', p_standard, 'model_strong', p_strong));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_pauses()
        RETURNS TABLE (tenant_id uuid, name text, reason text, paused_by text,
                       paused_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT p.tenant_id, t.name, p.reason, p.paused_by, p.paused_at
            FROM app.platform_ai_pauses p JOIN app.tenants t ON t.id = p.tenant_id
            ORDER BY p.paused_at DESC;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_pause(p_tenant uuid, p_paused boolean, p_reason text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            IF p_paused THEN
                IF p_reason IS NULL OR length(p_reason) < 3 THEN
                    RAISE EXCEPTION 'reason_required' USING ERRCODE = 'P0001';
                END IF;
                INSERT INTO app.platform_ai_pauses (tenant_id, reason, paused_by)
                VALUES (p_tenant, p_reason, v_email)
                ON CONFLICT (tenant_id) DO UPDATE
                SET reason = excluded.reason, paused_by = excluded.paused_by, paused_at = now();
            ELSE
                DELETE FROM app.platform_ai_pauses WHERE tenant_id = p_tenant;
            END IF;
            PERFORM app.platform_audit_add(
                CASE WHEN p_paused THEN 'ai.paused' ELSE 'ai.resumed' END, p_tenant,
                jsonb_build_object('reason', p_reason));
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (p_tenant, 'platform', app.current_user_id(),
                    CASE WHEN p_paused THEN 'ai.paused' ELSE 'ai.resumed' END,
                    jsonb_build_object('email', v_email));
        END
        $$
    """)
    # The cost board: AI credits per business over the window and the one before it.
    op.execute("""
        CREATE FUNCTION app.platform_ai_costs(p_days integer)
        RETURNS TABLE (tenant_id uuid, name text, currency text, modules text[],
                       credits numeric, previous_credits numeric, paused boolean)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('usage.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT t.id, t.name, t.currency::text,
                   coalesce((SELECT array_agg(m.module_key ORDER BY m.module_key)
                             FROM app.tenant_modules m WHERE m.tenant_id = t.id),
                            '{}'::text[]),
                   coalesce((SELECT sum(u.quantity) FROM app.usage_events u
                             WHERE u.tenant_id = t.id AND u.meter = 'ai_credits'
                               AND u.occurred_at > now() - make_interval(days => p_days)), 0),
                   coalesce((SELECT sum(u.quantity) FROM app.usage_events u
                             WHERE u.tenant_id = t.id AND u.meter = 'ai_credits'
                               AND u.occurred_at <= now() - make_interval(days => p_days)
                               AND u.occurred_at > now() - make_interval(days => 2 * p_days)),
                            0),
                   EXISTS (SELECT 1 FROM app.platform_ai_pauses p WHERE p.tenant_id = t.id)
            FROM app.tenants t
            ORDER BY 5 DESC, t.name;
        END
        $$
    """)
    # Every tool call of the console assistant is logged as the AI acting for a team member.
    op.execute("""
        CREATE FUNCTION app.platform_ai_audit(p_action text, p_tenant uuid, p_details jsonb)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            PERFORM app.platform_audit_add(
                'ai.tool.' || left(p_action, 60), p_tenant,
                coalesce(p_details, '{}') || jsonb_build_object('actor_type', 'ai'));
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.platform_ai_conversations, app.platform_ai_pauses")
    op.execute("DROP TABLE app.platform_ai_settings")
