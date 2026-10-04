"""Modules per business, and the platform console (platform admins see all businesses).

Platform admins are not tenant members: they read cross-tenant summaries only through
SECURITY DEFINER functions that check `app.is_platform_admin()`, never through table access.
Admins are granted by hand (SQL / the staging workflow), never through the API.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Businesses that existed before modules keep everything they could already use.
EXISTING_MODULES = ("client_app", "ai_pro")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.tenant_modules (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            module_key  text NOT NULL,
            quantity    integer NOT NULL DEFAULT 1 CHECK (quantity BETWEEN 1 AND 50),
            enabled_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, module_key)
        )
    """)
    op.execute(f"""
        INSERT INTO app.tenant_modules (tenant_id, module_key)
        SELECT t.id, m.key FROM app.tenants t, unnest(ARRAY{list(EXISTING_MODULES)}) AS m(key)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.tenant_modules TO app_api")
    op.execute("ALTER TABLE app.tenant_modules ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_modules_tenant ON app.tenant_modules TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # The client app checks the business has the client-app module.
    op.execute("""
        CREATE POLICY tenant_modules_client_select ON app.tenant_modules FOR SELECT TO app_api
        USING (tenant_id = app.client_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.platform_admins (
            user_id     uuid PRIMARY KEY REFERENCES app.users (id) ON DELETE CASCADE,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE app.platform_admins ENABLE ROW LEVEL SECURITY")  # no API access

    op.execute("""
        CREATE FUNCTION app.is_platform_admin() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM app.platform_admins WHERE user_id = app.current_user_id()
            )
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_businesses()
        RETURNS TABLE (
            id uuid, name text, vertical text, locale text, currency text, time_zone text,
            created_at timestamptz, members integer, clients integer, active_clients integer,
            modules text[], ai_credits_30d numeric, bookings_30d integer, owner_email text
        )
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT t.id, t.name, t.vertical, t.locale, t.currency::text, t.time_zone, t.created_at,
                (SELECT count(*)::int FROM app.tenant_members m WHERE m.tenant_id = t.id),
                (SELECT count(*)::int FROM app.clients c WHERE c.tenant_id = t.id),
                (SELECT count(DISTINCT e.client_id)::int FROM app.entitlements e
                 WHERE e.tenant_id = t.id AND e.status = 'active'
                   AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on),
                coalesce((SELECT array_agg(tm.module_key ORDER BY tm.module_key)
                          FROM app.tenant_modules tm WHERE tm.tenant_id = t.id), '{}'),
                coalesce((SELECT sum(u.quantity) FROM app.usage_events u
                          WHERE u.tenant_id = t.id AND u.meter = 'ai_credits'
                            AND u.occurred_at > now() - interval '30 days'), 0),
                (SELECT count(*)::int FROM app.bookings b
                 WHERE b.tenant_id = t.id AND b.created_at > now() - interval '30 days'),
                (SELECT u.email FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                 WHERE m.tenant_id = t.id AND m.role = 'owner' ORDER BY m.created_at LIMIT 1)
            FROM app.tenants t
            ORDER BY t.created_at DESC;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_usage(p_tenant_id uuid, p_days integer)
        RETURNS TABLE (day date, meter text, quantity numeric)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT u.occurred_at::date, u.meter, sum(u.quantity)
            FROM app.usage_events u
            WHERE (p_tenant_id IS NULL OR u.tenant_id = p_tenant_id)
              AND u.occurred_at > now() - make_interval(days => p_days)
            GROUP BY 1, 2 ORDER BY 1, 2;
        END
        $$
    """)
    # The public join-code lookup also says whether the business offers the client app.
    op.execute("DROP FUNCTION app.business_by_join_code(text)")
    op.execute("""
        CREATE FUNCTION app.business_by_join_code(p_code text)
        RETURNS TABLE (id uuid, name text, locale text, primary_color text,
                       logo_updated_at timestamptz, client_app boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id, t.name, t.locale, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END,
                   EXISTS (SELECT 1 FROM app.tenant_modules m
                           WHERE m.tenant_id = t.id AND m.module_key = 'client_app')
            FROM app.tenants t WHERE t.join_code = upper(trim(p_code))
        $$
    """)
    functions = (
        "is_platform_admin()",
        "platform_businesses()",
        "platform_usage(uuid, integer)",
        "business_by_join_code(text)",
    )
    for function in functions:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.business_by_join_code(text)")
    op.execute("""
        CREATE FUNCTION app.business_by_join_code(p_code text)
        RETURNS TABLE (id uuid, name text, locale text, primary_color text,
                       logo_updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id, t.name, t.locale, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END
            FROM app.tenants t WHERE t.join_code = upper(trim(p_code))
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.business_by_join_code(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.business_by_join_code(text) TO app_api")
    op.execute("DROP FUNCTION app.platform_usage(uuid, integer)")
    op.execute("DROP FUNCTION app.platform_businesses()")
    op.execute("DROP FUNCTION app.is_platform_admin()")
    op.execute("DROP TABLE app.platform_admins")
    op.execute("DROP TABLE app.tenant_modules")
