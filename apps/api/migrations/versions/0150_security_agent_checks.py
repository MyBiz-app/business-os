"""Read-only database checks for the security agent (slice C5).

`platform_security_db_checks()` looks only at the structure of the `app` schema (tables, row level
security, function owners and grants), never at rows of any business. It needs the same console
permission as the security reports. This only adds a function; nothing is changed or dropped.

Revision ID: 0150
Revises: 0149
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0150"
down_revision: str | None = "0149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = "platform_security_db_checks()"


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION app.{FUNCTION}
        RETURNS TABLE (check_name text, severity text, subject text, detail text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('incidents.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            -- Tables the API role can reach but no row level security protects.
            RETURN QUERY
            SELECT 'table_without_rls',
                   CASE WHEN EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
                                     WHERE a.attrelid = c.oid AND a.attname = 'tenant_id'
                                       AND NOT a.attisdropped) THEN 'high' ELSE 'medium' END,
                   c.relname::text,
                   'The API role can read or write this table and row level security is off'
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'app'
            WHERE c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
              AND pg_catalog.has_table_privilege('app_api', c.oid, 'SELECT,INSERT,UPDATE,DELETE');
            -- Functions that run with their owner's rights and could be steered by search_path.
            RETURN QUERY
            SELECT 'definer_without_search_path', 'high', p.proname::text,
                   'SECURITY DEFINER function without a fixed search_path'
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace AND n.nspname = 'app'
            WHERE p.prosecdef
              AND NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{{}}'::text[])) s
                              WHERE s LIKE 'search_path=%');
            -- Owner-rights functions anyone may call, including people who are not signed in.
            RETURN QUERY
            SELECT 'definer_open_to_public', 'high', p.proname::text,
                   'SECURITY DEFINER function that every database role may execute'
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace AND n.nspname = 'app'
            WHERE p.prosecdef
              AND EXISTS (SELECT 1
                          FROM pg_catalog.aclexplode(
                              coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
                          WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE');
            -- What was looked at, so a clean result is not mistaken for no result.
            RETURN QUERY
            SELECT 'checked_tables', 'info', 'app',
                   count(*)::text || ' tables'
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'app'
            WHERE c.relkind IN ('r', 'p');
            RETURN QUERY
            SELECT 'checked_functions', 'info', 'app',
                   count(*)::text || ' SECURITY DEFINER functions'
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace AND n.nspname = 'app'
            WHERE p.prosecdef;
        END
        $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION app.{FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app.{FUNCTION} TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops what was added; the previous release never calls it.
    op.execute(f"DROP FUNCTION app.{FUNCTION}")
