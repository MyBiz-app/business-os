"""The console AI agents map (slice C1): what the team changed about each agent.

The catalog of console agents lives in code (`app/ai/console_agents.py`). This table only holds
the team's changes: switched off, a name of their own, extra instructions that are always added
to the agent's prompt, and a place on the map. Like the other console AI settings it is not
reachable from the API role: only SECURITY DEFINER functions touch it, and they check the
console permission. Every change is written to the console audit log.

Console conversations may now be with any of the twelve agents, so the role check of
`platform_ai_conversations` is widened (the five old roles stay valid).

Revision ID: 0145
Revises: 0144
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0145"
down_revision: str | None = "0144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = ("manager", "support", "health", "billing", "growth")
ROLES = (
    *OLD_ROLES,
    "legal",
    "accountant",
    "market",
    "security",
    "product",
    "success",
    "marketing",
)
FUNCTIONS = (
    "platform_ai_agents()",
    "platform_ai_agent_set(text, boolean, text, text, text, numeric, numeric, text)",
)


def _roles(roles: tuple[str, ...]) -> str:
    return ", ".join(f"'{r}'" for r in roles)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.platform_ai_agents (
            agent_key          text PRIMARY KEY CHECK (agent_key IN ({_roles(ROLES)})),
            enabled            boolean NOT NULL DEFAULT true,
            name_he            text CHECK (length(name_he) BETWEEN 1 AND 60),
            name_en            text CHECK (length(name_en) BETWEEN 1 AND 60),
            -- Always added to the agent's prompt, written by the MyBiz team.
            extra_instructions text CHECK (length(extra_instructions) <= 2000),
            -- A place on the map in percent of the stage; null: the automatic place.
            map_x              numeric CHECK (map_x BETWEEN 0 AND 100),
            map_y              numeric CHECK (map_y BETWEEN 0 AND 100),
            -- A portrait the team supplies (an https address); null: the colour and initial.
            portrait_url       text
                               CHECK (portrait_url ~ '^https://' AND length(portrait_url) <= 500),
            updated_by         text NOT NULL,
            updated_at         timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE app.platform_ai_agents ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON app.platform_ai_agents FROM app_api")

    # Widen the role check: the old roles stay valid.
    op.execute(
        "ALTER TABLE app.platform_ai_conversations "
        "DROP CONSTRAINT platform_ai_conversations_role_check"
    )
    op.execute(
        "ALTER TABLE app.platform_ai_conversations ADD CONSTRAINT "
        f"platform_ai_conversations_role_check CHECK (role IN ({_roles(ROLES)}))"
    )

    op.execute("""
        CREATE FUNCTION app.platform_ai_agents()
        RETURNS TABLE (agent_key text, enabled boolean, name_he text, name_en text,
                       extra_instructions text, map_x numeric, map_y numeric,
                       portrait_url text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT a.agent_key, a.enabled, a.name_he, a.name_en, a.extra_instructions,
                   a.map_x, a.map_y, a.portrait_url
            FROM app.platform_ai_agents a ORDER BY a.agent_key;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_ai_agent_set(
            p_key text, p_enabled boolean, p_name_he text, p_name_en text,
            p_instructions text, p_x numeric, p_y numeric, p_portrait text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_ai_agents
                (agent_key, enabled, name_he, name_en, extra_instructions,
                 map_x, map_y, portrait_url, updated_by)
            VALUES (p_key, p_enabled, nullif(trim(p_name_he), ''), nullif(trim(p_name_en), ''),
                    nullif(trim(p_instructions), ''), p_x, p_y, nullif(trim(p_portrait), ''),
                    v_email)
            ON CONFLICT (agent_key) DO UPDATE
            SET enabled = excluded.enabled, name_he = excluded.name_he,
                name_en = excluded.name_en, extra_instructions = excluded.extra_instructions,
                map_x = excluded.map_x, map_y = excluded.map_y,
                portrait_url = excluded.portrait_url,
                updated_by = excluded.updated_by, updated_at = now();
            PERFORM app.platform_audit_add(
                'ai.agent', NULL,
                jsonb_build_object('agent', p_key, 'enabled', p_enabled,
                                   'has_instructions', coalesce(trim(p_instructions), '') <> ''));
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops the table and the functions, and the previous release never
    # reads them; conversations with the new roles are removed so the old check can return.
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.platform_ai_agents")
    op.execute(f"DELETE FROM app.platform_ai_conversations WHERE role NOT IN ({_roles(OLD_ROLES)})")
    op.execute(
        "ALTER TABLE app.platform_ai_conversations "
        "DROP CONSTRAINT platform_ai_conversations_role_check"
    )
    op.execute(
        "ALTER TABLE app.platform_ai_conversations ADD CONSTRAINT "
        f"platform_ai_conversations_role_check CHECK (role IN ({_roles(OLD_ROLES)}))"
    )
