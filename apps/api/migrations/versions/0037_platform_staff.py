"""MyBiz's own team: levels and permissions for the console, and an audit log of what the team
does. Replaces app.platform_admins (whose admins become owners).

Levels: the primary owner (one, cannot be removed, changed or disabled by anyone), owners
(everything, including managing owners and managers), managers (manage employees and give
them permissions the manager holds) and employees (only their permissions). Staff are
identified by their sign-in email, so they can be added before their first sign-in. The
rules live in SECURITY DEFINER functions; the tables are not reachable from the API.

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIMARY_OWNER = "adire7399@gmail.com"  # decided by the owner (T64); identified by email only
PERMISSIONS = (
    "businesses.read",  # every business: details, owners, team, clients
    "businesses.act",  # enter a business and work in it (audited, visible to its owner)
    "billing.manage",  # trials, modules, invoices
    "inbox.manage",  # contact requests and complaints
    "usage.read",  # AI usage and revenue
    "staff.manage",  # managers: manage employees
)
FUNCTIONS = (
    "platform_me()",
    "platform_can(text)",
    "platform_staff_list()",
    "platform_staff_save(text, text, text[], boolean)",
    "platform_staff_remove(text)",
    "platform_audit_add(text, uuid, jsonb)",
    "platform_audit_list(integer)",
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.platform_staff (
            email        text PRIMARY KEY CHECK (email = lower(email) AND length(email) <= 254),
            level        text NOT NULL
                         CHECK (level IN ('primary_owner', 'owner', 'manager', 'employee')),
            permissions  text[] NOT NULL DEFAULT '{{}}'
                         CHECK (permissions <@ ARRAY{list(PERMISSIONS)}::text[]),
            disabled     boolean NOT NULL DEFAULT false,
            added_by     text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            CHECK (level <> 'primary_owner' OR NOT disabled)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX platform_staff_one_primary_owner ON app.platform_staff ((true))
        WHERE level = 'primary_owner'
    """)
    op.execute("ALTER TABLE app.platform_staff ENABLE ROW LEVEL SECURITY")  # no API access
    op.execute("""
        INSERT INTO app.platform_staff (email, level, added_by)
        SELECT lower(u.email), 'owner', 'migration'
        FROM app.platform_admins a JOIN app.users u ON u.id = a.user_id
        WHERE coalesce(u.email, '') <> ''
        ON CONFLICT DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO app.platform_staff (email, level, added_by)
        VALUES ('{PRIMARY_OWNER}', 'primary_owner', 'migration')
        ON CONFLICT (email) DO UPDATE SET level = 'primary_owner', disabled = false
    """)

    op.execute("""
        CREATE TABLE app.platform_audit (
            id           bigserial PRIMARY KEY,
            occurred_at  timestamptz NOT NULL DEFAULT now(),
            actor_email  text NOT NULL,
            action       text NOT NULL,
            business_id  uuid REFERENCES app.tenants (id) ON DELETE SET NULL,
            details      jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX platform_audit_time ON app.platform_audit (occurred_at DESC)")
    op.execute("ALTER TABLE app.platform_audit ENABLE ROW LEVEL SECURITY")  # no API access

    # Who am I on the MyBiz team? Owners hold every permission.
    op.execute(f"""
        CREATE FUNCTION app.platform_me()
        RETURNS TABLE (email text, level text, permissions text[])
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT s.email, s.level,
                   CASE WHEN s.level IN ('primary_owner', 'owner')
                        THEN ARRAY{list(PERMISSIONS)}::text[] ELSE s.permissions END
            FROM app.platform_staff s
            JOIN app.users u ON lower(u.email) = s.email
            WHERE u.id = app.current_user_id() AND NOT s.disabled
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app.is_platform_admin() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$ SELECT EXISTS (SELECT 1 FROM app.platform_me()) $$
    """)
    op.execute("DROP TABLE app.platform_admins")
    op.execute("""
        CREATE FUNCTION app.platform_can(p_permission text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM app.platform_me() m WHERE p_permission = ANY(m.permissions)
            )
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_audit_add(p_action text, p_tenant uuid, p_details jsonb)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF v_email IS NULL THEN
                RAISE EXCEPTION 'platform_only' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_audit (actor_email, action, business_id, details)
            VALUES (v_email, p_action, p_tenant, coalesce(p_details, '{}'));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_audit_list(p_limit integer)
        RETURNS TABLE (occurred_at timestamptz, actor_email text, action text, tenant_id uuid,
                       tenant_name text, details jsonb)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM app.platform_me() m
                           WHERE m.level IN ('primary_owner', 'owner')) THEN
                RAISE EXCEPTION 'owners_only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT a.occurred_at, a.actor_email, a.action, a.business_id, t.name, a.details
            FROM app.platform_audit a LEFT JOIN app.tenants t ON t.id = a.business_id
            ORDER BY a.occurred_at DESC, a.id DESC LIMIT least(p_limit, 500);
        END
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_staff_list()
        RETURNS TABLE (email text, level text, permissions text[], disabled boolean,
                       full_name text, signed_up boolean, added_by text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('staff.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT s.email, s.level, s.permissions, s.disabled, u.full_name, u.id IS NOT NULL,
                   s.added_by, s.created_at
            FROM app.platform_staff s
            LEFT JOIN app.users u ON lower(u.email) = s.email
            ORDER BY array_position(ARRAY['primary_owner', 'owner', 'manager', 'employee'],
                                    s.level), s.email;
        END
        $$
    """)
    # The rules for changing the team. Every level only gives what it holds; nobody touches
    # the primary owner or their own entry; only owners add or change owners and managers.
    op.execute("""
        CREATE FUNCTION app.platform_may_manage(p_actor_level text, p_target_level text)
        RETURNS boolean
        LANGUAGE sql IMMUTABLE SET search_path = ''
        AS $$
            SELECT CASE
                WHEN p_target_level = 'primary_owner' THEN false
                WHEN p_actor_level IN ('primary_owner', 'owner') THEN true
                WHEN p_actor_level = 'manager' THEN p_target_level = 'employee'
                ELSE false
            END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_staff_save(
            p_email text, p_level text, p_permissions text[], p_disabled boolean
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_me record;
            v_email text := lower(trim(p_email));
            v_current text;
            v_permissions text[] := coalesce(p_permissions, '{}');
        BEGIN
            SELECT * INTO v_me FROM app.platform_me();
            IF v_me IS NULL OR NOT 'staff.manage' = ANY(v_me.permissions) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF v_email = v_me.email THEN
                RAISE EXCEPTION 'not_yourself' USING ERRCODE = '42501';
            END IF;
            SELECT level INTO v_current FROM app.platform_staff WHERE email = v_email;
            IF v_current = 'primary_owner' THEN
                RAISE EXCEPTION 'primary_owner_protected' USING ERRCODE = '42501';
            END IF;
            IF NOT app.platform_may_manage(v_me.level, p_level)
               OR (v_current IS NOT NULL
                   AND NOT app.platform_may_manage(v_me.level, v_current)) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF p_level IN ('owner') THEN
                v_permissions := '{}';  -- owners hold everything
            END IF;
            IF p_level = 'employee' AND 'staff.manage' = ANY(v_permissions) THEN
                RAISE EXCEPTION 'employees_do_not_manage_staff' USING ERRCODE = 'P0001';
            END IF;
            IF NOT v_permissions <@ v_me.permissions THEN
                RAISE EXCEPTION 'cannot_grant_more_than_you_hold' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_staff (email, level, permissions, disabled, added_by)
            VALUES (v_email, p_level, v_permissions, coalesce(p_disabled, false), v_me.email)
            ON CONFLICT (email) DO UPDATE
                SET level = excluded.level, permissions = excluded.permissions,
                    disabled = excluded.disabled, updated_at = now();
            PERFORM app.platform_audit_add(
                CASE WHEN v_current IS NULL THEN 'staff.added' ELSE 'staff.changed' END, NULL,
                jsonb_build_object('email', v_email, 'level', p_level,
                                   'permissions', to_jsonb(v_permissions),
                                   'disabled', coalesce(p_disabled, false)));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_staff_remove(p_email text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_me record;
            v_email text := lower(trim(p_email));
            v_current text;
        BEGIN
            SELECT * INTO v_me FROM app.platform_me();
            IF v_me IS NULL OR NOT 'staff.manage' = ANY(v_me.permissions) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF v_email = v_me.email THEN
                RAISE EXCEPTION 'not_yourself' USING ERRCODE = '42501';
            END IF;
            SELECT level INTO v_current FROM app.platform_staff WHERE email = v_email;
            IF v_current IS NULL THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            IF v_current = 'primary_owner' THEN
                RAISE EXCEPTION 'primary_owner_protected' USING ERRCODE = '42501';
            END IF;
            IF NOT app.platform_may_manage(v_me.level, v_current) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            DELETE FROM app.platform_staff WHERE email = v_email;
            PERFORM app.platform_audit_add(
                'staff.removed', NULL, jsonb_build_object('email', v_email, 'level', v_current));
        END
        $$
    """)
    # The primary owner is a bunker: even direct SQL through the API role can't touch it.
    op.execute("""
        CREATE FUNCTION app.protect_primary_owner() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            IF OLD.level = 'primary_owner' AND (TG_OP = 'DELETE' OR NEW.level <> 'primary_owner'
                                                 OR NEW.email <> OLD.email OR NEW.disabled) THEN
                RAISE EXCEPTION 'primary_owner_protected' USING ERRCODE = '42501';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER platform_staff_primary_owner BEFORE UPDATE OR DELETE ON app.platform_staff
        FOR EACH ROW EXECUTE FUNCTION app.protect_primary_owner()
    """)

    for function in (*FUNCTIONS, "platform_may_manage(text, text)"):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
    for function in FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    op.execute("DROP TRIGGER platform_staff_primary_owner ON app.platform_staff")
    op.execute("DROP FUNCTION app.protect_primary_owner()")
    for function in (
        "platform_staff_remove(text)",
        "platform_staff_save(text, text, text[], boolean)",
        "platform_may_manage(text, text)",
        "platform_staff_list()",
        "platform_audit_list(integer)",
        "platform_audit_add(text, uuid, jsonb)",
        "platform_can(text)",
    ):
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("""
        CREATE TABLE app.platform_admins (
            user_id     uuid PRIMARY KEY REFERENCES app.users (id) ON DELETE CASCADE,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE app.platform_admins ENABLE ROW LEVEL SECURITY")
    op.execute("""
        INSERT INTO app.platform_admins (user_id)
        SELECT u.id FROM app.platform_staff s JOIN app.users u ON lower(u.email) = s.email
        WHERE s.level IN ('primary_owner', 'owner') AND NOT s.disabled
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app.is_platform_admin() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM app.platform_admins WHERE user_id = app.current_user_id()
            )
        $$
    """)
    op.execute("DROP FUNCTION app.platform_me()")
    op.execute("DROP TABLE app.platform_audit")
    op.execute("DROP TABLE app.platform_staff")
