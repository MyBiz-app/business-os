"""Guards on the database itself, so a new table or function can't quietly skip the rules."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

# Tables without tenant_id that are still protected by RLS (their own policies).
GLOBAL_TABLES = {"tenants", "users", "platform_admins", "contact_requests"}


def _query(engine: Engine, sql: str) -> list:
    with engine.connect() as connection:
        return connection.execute(text(sql)).all()


def test_every_table_has_row_level_security(engine: Engine) -> None:
    tables = _query(
        engine,
        """
        SELECT c.relname, c.relrowsecurity,
               EXISTS (SELECT 1 FROM pg_attribute a
                       WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped),
               coalesce((SELECT bool_or(pg_get_expr(p.polqual, p.polrelid) LIKE '%tenant%'
                                        OR pg_get_expr(p.polwithcheck, p.polrelid) LIKE '%tenant%'
                                        OR pg_get_expr(p.polqual, p.polrelid) LIKE '%client%')
                         FROM pg_policy p WHERE p.polrelid = c.oid), false)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'app' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
        """,
    )
    assert tables
    assert [name for name, rls, _, _ in tables if not rls] == []
    tenant_tables = [(name, scoped) for name, _, has_tenant, scoped in tables if has_tenant]
    assert [name for name, scoped in tenant_tables if not scoped] == []
    assert {name for name, _, has_tenant, _ in tables if not has_tenant} <= GLOBAL_TABLES


def test_security_definer_functions_pin_search_path(engine: Engine) -> None:
    unpinned = _query(
        engine,
        """
        SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'app' AND p.prosecdef
          AND NOT coalesce(p.proconfig::text LIKE '%search_path=%', false)
        """,
    )
    assert unpinned == []


def test_public_roles_cannot_reach_app_tables(engine: Engine) -> None:
    # Supabase's anon/authenticated roles (and PUBLIC) must never read app data directly.
    grants = _query(
        engine,
        """
        SELECT grantee, table_name FROM information_schema.role_table_grants
        WHERE table_schema = 'app' AND grantee IN ('PUBLIC', 'anon', 'authenticated')
        """,
    )
    assert grants == []


def test_api_sends_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
