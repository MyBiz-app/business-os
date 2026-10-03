"""Tenancy core: users, tenants, tenant members, with row-level security.

Revision ID: 0001
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The API runs every request as `app_api` (via SET LOCAL ROLE). The role cannot log in and
    # does not bypass row-level security, so the policies below always apply to the API.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_api') THEN
                CREATE ROLE app_api NOLOGIN NOBYPASSRLS;
            END IF;
        END
        $$;
    """)
    op.execute("GRANT app_api TO CURRENT_USER")

    # App tables live in their own schema, which Supabase does not expose to browsers.
    op.execute("CREATE SCHEMA app")
    op.execute("GRANT USAGE ON SCHEMA app TO app_api")

    op.execute("""
        CREATE TABLE app.users (
            id          uuid PRIMARY KEY,
            email       text NOT NULL,
            full_name   text,
            locale      text,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.tenants (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name        text NOT NULL CHECK (length(trim(name)) > 0),
            vertical    text NOT NULL,
            locale      text NOT NULL,
            time_zone   text NOT NULL,
            currency    char(3) NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.tenant_members (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            role        text NOT NULL CHECK (role IN ('owner', 'manager', 'staff', 'front_desk')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, user_id)
        )
    """)
    op.execute("CREATE INDEX tenant_members_user_id_idx ON app.tenant_members (user_id)")

    # Request context, set by the API per transaction with set_config(..., true).
    op.execute("""
        CREATE FUNCTION app.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE
        AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$
    """)
    # Returns the requested tenant only if the current user is a member of it, so a forged
    # tenant id never grants access. SECURITY DEFINER lets it read memberships past RLS.
    op.execute("""
        CREATE FUNCTION app.current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT m.tenant_id
            FROM app.tenant_members m
            WHERE m.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND m.user_id = app.current_user_id()
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.is_member(p_tenant_id uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM app.tenant_members m
                WHERE m.tenant_id = p_tenant_id AND m.user_id = app.current_user_id()
            )
        $$
    """)
    # Creating a tenant and its first owner is one atomic, server-side operation.
    op.execute("""
        CREATE FUNCTION app.create_tenant(
            p_name text, p_vertical text, p_locale text, p_time_zone text, p_currency text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user_id uuid := app.current_user_id();
            v_tenant_id uuid;
        BEGIN
            IF v_user_id IS NULL THEN
                RAISE EXCEPTION 'no current user' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.tenants (name, vertical, locale, time_zone, currency)
            VALUES (p_name, p_vertical, p_locale, p_time_zone, p_currency)
            RETURNING id INTO v_tenant_id;
            INSERT INTO app.tenant_members (tenant_id, user_id, role)
            VALUES (v_tenant_id, v_user_id, 'owner');
            RETURN v_tenant_id;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.create_tenant(text, text, text, text, text) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.create_tenant(text, text, text, text, text) TO app_api"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE ON app.users TO app_api")
    op.execute("GRANT SELECT, UPDATE ON app.tenants TO app_api")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.tenant_members TO app_api")

    for table in ("users", "tenants", "tenant_members"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY users_self ON app.users TO app_api
        USING (id = app.current_user_id())
        WITH CHECK (id = app.current_user_id())
    """)
    op.execute("""
        CREATE POLICY tenants_select ON app.tenants FOR SELECT TO app_api
        USING (app.is_member(id))
    """)
    op.execute("""
        CREATE POLICY tenants_update ON app.tenants FOR UPDATE TO app_api
        USING (id = app.current_tenant_id())
        WITH CHECK (id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY tenant_members_select ON app.tenant_members FOR SELECT TO app_api
        USING (user_id = app.current_user_id() OR tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY tenant_members_write ON app.tenant_members TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP SCHEMA app CASCADE")
