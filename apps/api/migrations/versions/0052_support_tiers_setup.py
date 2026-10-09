"""Deliver the support and setup tiers sold in the sign-up journey (#104).

Requests from a business with priority or VIP support come first in the console's inbox, and
each one shows its tier. Buying setup (guided or done for us) opens a task in the same inbox,
once per business and kind, so the MyBiz team knows to reach out; the one-time fee itself is
already billed with the first invoice.

Revision ID: 0052
Revises: 0051
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.contact_requests
            ADD COLUMN kind text NOT NULL DEFAULT 'request'
                CHECK (kind IN ('request', 'setup_guided', 'setup_full'))
    """)

    # A setup module saved for a business opens a task for the MyBiz team. Modules are saved by
    # replacing them, so the task is opened only once per business and kind.
    op.execute("""
        CREATE FUNCTION app.open_setup_task() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_owner record;
        BEGIN
            IF NEW.module_key NOT IN ('setup_guided', 'setup_full') OR EXISTS (
                SELECT 1 FROM app.contact_requests r
                WHERE r.tenant_id = NEW.tenant_id AND r.kind = NEW.module_key
            ) THEN
                RETURN NEW;
            END IF;
            -- The business's first owner, or whoever is buying when it has none yet.
            SELECT u.email, u.full_name INTO v_owner
            FROM app.users u
            WHERE u.id = coalesce((
                SELECT m.user_id FROM app.tenant_members m
                WHERE m.tenant_id = NEW.tenant_id AND m.role = 'owner'
                ORDER BY m.created_at LIMIT 1
            ), app.current_user_id());
            INSERT INTO app.contact_requests (name, email, business, locale, tenant_id, kind)
            SELECT coalesce(nullif(trim(v_owner.full_name), ''), split_part(v_owner.email, '@', 1),
                            t.name),
                   lower(coalesce(v_owner.email, 'unknown@mybiz.invalid')), t.name, t.locale,
                   t.id, NEW.module_key
            FROM app.tenants t WHERE t.id = NEW.tenant_id;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER tenant_modules_setup_task AFTER INSERT ON app.tenant_modules
        FOR EACH ROW EXECUTE FUNCTION app.open_setup_task()
    """)
    op.execute("REVOKE ALL ON FUNCTION app.open_setup_task() FROM PUBLIC")

    # The inbox shows each request's kind and the business's support tier, and the tier orders
    # open requests: VIP, then priority, then standard (site requests count as standard).
    op.execute("DROP FUNCTION app.platform_contact_requests()")
    op.execute("""
        CREATE FUNCTION app.platform_contact_requests()
        RETURNS TABLE (id uuid, name text, email text, phone text, business text, vertical text,
                       message text, locale text, created_at timestamptz, status text,
                       assignee text, notes text, tenant_id uuid, from_business boolean,
                       kind text, tier text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('inbox.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.name, r.email, r.phone, r.business, r.vertical, r.message, r.locale,
                   r.created_at, r.status, r.assignee, r.notes, r.tenant_id,
                   r.tenant_id IS NOT NULL, r.kind, tier.value
            FROM app.contact_requests r
            CROSS JOIN LATERAL (
                SELECT CASE
                    WHEN EXISTS (SELECT 1 FROM app.tenant_modules m WHERE m.tenant_id = r.tenant_id
                                 AND m.module_key = 'support_vip') THEN 'vip'
                    WHEN EXISTS (SELECT 1 FROM app.tenant_modules m WHERE m.tenant_id = r.tenant_id
                                 AND m.module_key = 'support_priority') THEN 'priority'
                    ELSE 'standard' END AS value
            ) tier
            ORDER BY array_position(ARRAY['new', 'in_progress', 'done'], r.status),
                     CASE WHEN r.status = 'done' THEN 0
                          ELSE array_position(ARRAY['vip', 'priority', 'standard'], tier.value)
                     END,
                     r.created_at DESC
            LIMIT 300;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_contact_requests() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_contact_requests() TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_contact_requests()")
    op.execute("""
        CREATE FUNCTION app.platform_contact_requests()
        RETURNS TABLE (id uuid, name text, email text, phone text, business text, vertical text,
                       message text, locale text, created_at timestamptz, status text,
                       assignee text, notes text, tenant_id uuid, from_business boolean)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('inbox.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.name, r.email, r.phone, r.business, r.vertical, r.message, r.locale,
                   r.created_at, r.status, r.assignee, r.notes, r.tenant_id,
                   r.tenant_id IS NOT NULL
            FROM app.contact_requests r
            ORDER BY array_position(ARRAY['new', 'in_progress', 'done'], r.status),
                     r.created_at DESC
            LIMIT 300;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_contact_requests() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_contact_requests() TO app_api")
    op.execute("DROP TRIGGER tenant_modules_setup_task ON app.tenant_modules")
    op.execute("DROP FUNCTION app.open_setup_task()")
    op.execute("DELETE FROM app.contact_requests WHERE kind <> 'request'")
    op.execute("ALTER TABLE app.contact_requests DROP COLUMN kind")
