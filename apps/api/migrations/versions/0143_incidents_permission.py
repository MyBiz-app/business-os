"""A console permission of its own for incident banners, and a one-business lookup.

Incident banners (0121) used the `broadcasts.manage` permission, so anyone allowed to message
businesses could also put a banner on every page. They now need `incidents.manage`. People who held
`broadcasts.manage` keep banners by being given the new permission, so nobody loses access.

`app.platform_business(id)` returns one business with the same columns as
`app.platform_businesses()`, so the business card no longer loads every business to show one.

Revision ID: 0143
Revises: 0142
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0143"
down_revision: str | None = "0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PERMISSIONS = (
    "businesses.read",
    "businesses.act",
    "billing.manage",
    "inbox.manage",
    "usage.read",
    "staff.manage",
    "broadcasts.manage",
)
PERMISSIONS = (*OLD_PERMISSIONS, "incidents.manage")


def _me(permissions: tuple[str, ...]) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION app.platform_me()
        RETURNS TABLE (email text, level text, permissions text[])
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT s.email, s.level,
                   CASE WHEN s.level IN ('primary_owner', 'owner')
                        THEN ARRAY{list(permissions)}::text[] ELSE s.permissions END
            FROM app.platform_staff s
            JOIN app.users u ON lower(u.email) = s.email
            WHERE u.id = app.current_user_id() AND NOT s.disabled
        $$
    """


def _incident_functions(permission: str) -> None:
    """The three console functions of 0121, checking `permission`."""
    op.execute(f"""
        CREATE OR REPLACE FUNCTION app.incident_open(
            p_kind text, p_content jsonb, p_status_url text
        ) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('{permission}') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_incidents (kind, content, status_url, created_by)
            VALUES (p_kind, p_content, p_status_url, (SELECT m.email FROM app.platform_me() m))
            RETURNING platform_incidents.id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION app.incident_resolve(p_id uuid) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('{permission}') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.platform_incidents i
            SET resolved_at = now(), resolved_by = (SELECT m.email FROM app.platform_me() m)
            WHERE i.id = p_id AND i.resolved_at IS NULL
            RETURNING i.id INTO v_id;
            IF v_id IS NULL THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            RETURN v_id;
        END
        $$
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION app.incident_rows()
        RETURNS TABLE (id uuid, kind text, content jsonb, status_url text, created_by text,
                       created_at timestamptz, resolved_at timestamptz, resolved_by text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('{permission}') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT i.id, i.kind, i.content, i.status_url, i.created_by, i.created_at,
                   i.resolved_at, i.resolved_by
            FROM app.platform_incidents i
            ORDER BY i.created_at DESC LIMIT 50;
        END
        $$
    """)


def upgrade() -> None:
    op.execute("ALTER TABLE app.platform_staff DROP CONSTRAINT platform_staff_permissions_check")
    op.execute(f"""
        ALTER TABLE app.platform_staff ADD CONSTRAINT platform_staff_permissions_check
        CHECK (permissions <@ ARRAY{list(PERMISSIONS)}::text[])
    """)
    op.execute(_me(PERMISSIONS))
    op.execute("""
        UPDATE app.platform_staff
        SET permissions = array_append(permissions, 'incidents.manage')
        WHERE 'broadcasts.manage' = ANY(permissions) AND NOT 'incidents.manage' = ANY(permissions)
    """)
    _incident_functions("incidents.manage")

    op.execute("""
        CREATE FUNCTION app.platform_business(p_id uuid)
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
            WHERE t.id = p_id;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_business(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_business(uuid) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_business(uuid)")
    _incident_functions("broadcasts.manage")
    op.execute(_me(OLD_PERMISSIONS))
    op.execute("""
        UPDATE app.platform_staff SET permissions = array_remove(permissions, 'incidents.manage')
    """)
    op.execute("ALTER TABLE app.platform_staff DROP CONSTRAINT platform_staff_permissions_check")
    op.execute(f"""
        ALTER TABLE app.platform_staff ADD CONSTRAINT platform_staff_permissions_check
        CHECK (permissions <@ ARRAY{list(OLD_PERMISSIONS)}::text[])
    """)
