"""The console's inbox: contact requests from the marketing site and complaints from business
owners get a status (new, in progress, done), an owner on the MyBiz side and internal notes, so
nothing is answered twice or forgotten.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "platform_contact_requests()",
    "platform_inbox_update(uuid, text, text, text)",
    "submit_complaint(text, text)",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.contact_requests
            ADD COLUMN status text NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'in_progress', 'done')),
            ADD COLUMN assignee text CHECK (length(assignee) <= 254),
            ADD COLUMN notes text CHECK (length(notes) <= 4000),
            ADD COLUMN tenant_id uuid REFERENCES app.tenants (id) ON DELETE SET NULL,
            ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()
    """)
    op.execute("CREATE INDEX contact_requests_status ON app.contact_requests (status, created_at)")

    # A business owner's complaint from inside the app reaches the same inbox.
    op.execute("""
        CREATE FUNCTION app.submit_complaint(p_message text, p_locale text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_id uuid;
            v_tenant uuid := app.current_tenant_id();
            v_user record;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no_business' USING ERRCODE = '42501';
            END IF;
            SELECT u.email, u.full_name INTO v_user
            FROM app.users u WHERE u.id = app.current_user_id();
            IF v_user IS NULL THEN
                RAISE EXCEPTION 'no_user' USING ERRCODE = '42501';
            END IF;
            IF (SELECT count(*) FROM app.contact_requests
                WHERE tenant_id = v_tenant AND created_at > now() - interval '1 hour') >= 5 THEN
                RAISE EXCEPTION 'too_many_requests' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.contact_requests
                (name, email, business, message, locale, tenant_id)
            SELECT coalesce(nullif(trim(v_user.full_name), ''), split_part(v_user.email, '@', 1)),
                   lower(v_user.email), t.name, p_message, p_locale, v_tenant
            FROM app.tenants t WHERE t.id = v_tenant
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)

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
    op.execute("""
        CREATE FUNCTION app.platform_inbox_update(
            p_id uuid, p_status text, p_assignee text, p_notes text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_me text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('inbox.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.contact_requests
            SET status = coalesce(p_status, status),
                -- 'me' assigns to the caller; '' clears the assignee.
                assignee = CASE WHEN p_assignee IS NULL THEN assignee
                                WHEN p_assignee = 'me' THEN v_me
                                WHEN p_assignee = '' THEN NULL
                                ELSE lower(p_assignee) END,
                notes = coalesce(p_notes, notes),
                updated_at = now()
            WHERE id = p_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            PERFORM app.platform_audit_add(
                'inbox.updated', NULL,
                jsonb_build_object('request', p_id, 'status', p_status, 'assignee', p_assignee));
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_inbox_update(uuid, text, text, text)")
    op.execute("DROP FUNCTION app.submit_complaint(text, text)")
    op.execute("DROP FUNCTION app.platform_contact_requests()")
    op.execute("""
        CREATE FUNCTION app.platform_contact_requests()
        RETURNS TABLE (id uuid, name text, email text, phone text, business text, vertical text,
                       message text, locale text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.name, r.email, r.phone, r.business, r.vertical, r.message, r.locale,
                   r.created_at
            FROM app.contact_requests r ORDER BY r.created_at DESC LIMIT 200;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_contact_requests() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_contact_requests() TO app_api")
    op.execute("DROP INDEX app.contact_requests_status")
    op.execute("""
        ALTER TABLE app.contact_requests
            DROP COLUMN status, DROP COLUMN assignee, DROP COLUMN notes,
            DROP COLUMN tenant_id, DROP COLUMN updated_at
    """)
