"""Guards on the database itself, so a new table or function can't quietly skip the rules."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

# Tables without tenant_id that are still protected by RLS (their own policies).
GLOBAL_TABLES = {"tenants", "users", "platform_staff", "platform_audit"}
# Tables whose tenant_id only says which business a row is about: they are MyBiz's own, have no
# API access at all (RLS with no policy), and are read through SECURITY DEFINER functions.
PLATFORM_TABLES = {"contact_requests", "platform_audit"}


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
    tenant_tables = [
        (name, scoped)
        for name, _, has_tenant, scoped in tables
        if has_tenant and name not in PLATFORM_TABLES
    ]
    assert [name for name, scoped in tenant_tables if not scoped] == []
    assert {name for name, _, has_tenant, _ in tables if not has_tenant} <= GLOBAL_TABLES
    # MyBiz's own tables stay unreachable from the API role.
    own = tuple(sorted(PLATFORM_TABLES | {"platform_staff"}))
    reachable = _query(
        engine,
        f"""
        SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'app' AND c.relname IN {own}
          AND (EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid)
               OR has_table_privilege('app_api', c.oid, 'SELECT'))
        """,
    )
    assert reachable == []


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


def test_alembic_version_is_locked(engine: Engine) -> None:
    # Alembic keeps its table in `public`, which Supabase's Data API exposes.
    [(rls,)] = _query(
        engine,
        "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.alembic_version'::regclass",
    )
    assert rls
    grants = _query(
        engine,
        """
        SELECT grantee FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = 'alembic_version'
          AND grantee IN ('PUBLIC', 'anon', 'authenticated')
        """,
    )
    assert grants == []


def test_api_sends_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
