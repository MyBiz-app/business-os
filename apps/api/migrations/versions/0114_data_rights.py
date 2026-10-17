"""Data rights (go-live, GL8): whole-business export and platform invoices that outlive a business.

Exports: the owner asks for a ZIP of everything the business holds; it is built in the
background, kept 24 hours and downloaded through a signed link.

Invoices: MyBiz's invoices to a business must be kept 7 years, so they no longer cascade away
with the business. They keep the business's name and tax number as text, and lose the link
(`tenant_id` becomes null) when the business is deleted.

Revision ID: 0114
Revises: 0113
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0114"
down_revision: str | None = "0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.data_exports (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            requested_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            status       text NOT NULL DEFAULT 'building'
                             CHECK (status IN ('building', 'ready', 'failed')),
            content      bytea,
            storage_key  text,
            size         bigint,
            file_count   integer,
            created_at   timestamptz NOT NULL DEFAULT now(),
            ready_at     timestamptz,
            expires_at   timestamptz
        )
    """)
    op.execute("CREATE INDEX data_exports_tenant ON app.data_exports (tenant_id, created_at DESC)")
    op.execute("CREATE INDEX data_exports_requested_by ON app.data_exports (requested_by)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.data_exports TO app_api")
    op.execute("ALTER TABLE app.data_exports ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY data_exports_tenant ON app.data_exports TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # The signed download link opens a ZIP with no sign-in: one narrow read, tenant checked.
    op.execute("""
        CREATE FUNCTION app.data_export(p_id uuid, p_tenant uuid)
        RETURNS TABLE (content bytea, storage_key text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT e.content, e.storage_key FROM app.data_exports e
            WHERE e.id = p_id AND e.tenant_id = p_tenant AND e.status = 'ready'
              AND e.expires_at > now()
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.data_export(uuid, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.data_export(uuid, uuid) TO app_api")

    # Client data in tables the API role can't touch directly: delivery logs of announcements,
    # and the rows erasure removes in tables it can only read or write. Both check the tenant.
    op.execute("""
        CREATE FUNCTION app.client_announcement_deliveries(p_client uuid)
        RETURNS TABLE (channel text, status text, sent_at timestamptz,
                       unsubscribed_at timestamptz, created_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT d.channel, d.status, d.sent_at, d.unsubscribed_at, d.created_at
            FROM app.announcement_deliveries d
            WHERE d.client_id = p_client AND d.tenant_id = app.current_tenant_id()
            ORDER BY d.created_at
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.client_app_ai_conversations(p_client uuid)
        RETURNS TABLE (title text, messages jsonb, created_at timestamptz,
                       updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT c.title, c.messages, c.created_at, c.updated_at
            FROM app.ai_conversations c JOIN app.clients cl
              ON cl.user_id = c.user_id AND cl.tenant_id = c.tenant_id
            WHERE cl.id = p_client AND cl.tenant_id = app.current_tenant_id()
            ORDER BY c.created_at
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.erase_client_traces(p_client uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE v_tenant uuid := app.current_tenant_id();
        BEGIN
            DELETE FROM app.announcement_deliveries
            WHERE client_id = p_client AND tenant_id = v_tenant;
            DELETE FROM app.client_social WHERE client_id = p_client AND tenant_id = v_tenant;
            DELETE FROM app.whatsapp_offers WHERE client_id = p_client AND tenant_id = v_tenant;
            DELETE FROM app.ai_conversations c USING app.clients cl
            WHERE cl.id = p_client AND cl.tenant_id = v_tenant AND c.tenant_id = v_tenant
              AND cl.user_id = c.user_id;
        END $$
    """)
    for function in (
        "client_announcement_deliveries(uuid)",
        "client_app_ai_conversations(uuid)",
        "erase_client_traces(uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")

    # "Delete my account" (required by Apple and Google): the person is disconnected from every
    # business and their profile is emptied. The row stays, anonymous, because payroll and
    # accounting records of businesses point to it and must be kept. Client data a business
    # holds about them stays with the business (they can ask the business to erase it).
    op.execute("ALTER TABLE app.users ADD COLUMN deleted_at timestamptz")
    op.execute("""
        CREATE FUNCTION app.delete_my_account() RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE v_user uuid := app.current_user_id();
        BEGIN
            IF v_user IS NULL THEN
                RAISE EXCEPTION 'not signed in' USING ERRCODE = 'P0001';
            END IF;
            IF EXISTS (
                SELECT 1 FROM app.tenant_members m JOIN app.tenants t ON t.id = m.tenant_id
                WHERE m.user_id = v_user AND m.role = 'owner' AND t.closed_at IS NULL
            ) THEN
                RAISE EXCEPTION 'owns_business' USING ERRCODE = 'P0001';
            END IF;
            UPDATE app.clients SET user_id = NULL WHERE user_id = v_user;
            DELETE FROM app.tenant_members WHERE user_id = v_user;
            DELETE FROM app.push_tokens WHERE user_id = v_user;
            DELETE FROM app.ai_conversations WHERE user_id = v_user;
            DELETE FROM app.person_identities WHERE user_id = v_user;
            DELETE FROM app.announcement_views WHERE user_id = v_user;
            UPDATE app.users
            SET email = 'deleted-' || id || '@deleted.invalid', full_name = NULL, phone = NULL,
                birth_date = NULL, address_line = NULL, city = NULL, postal_code = NULL,
                avatar = NULL, avatar_content_type = NULL, avatar_updated_at = NULL,
                status_text = NULL, marketing_consent_at = NULL, deleted_at = now(),
                updated_at = now()
            WHERE id = v_user;
        END $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.delete_my_account() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.delete_my_account() TO app_api")

    # Platform invoices stay when the business is deleted (kept 7 years, with its name as text).
    op.execute("ALTER TABLE app.platform_invoices ADD COLUMN business_name text")
    op.execute("ALTER TABLE app.platform_invoices ADD COLUMN business_tax_id text")
    op.execute("""
        UPDATE app.platform_invoices i
        SET business_name = t.name,
            business_tax_id = (SELECT b.tax_id FROM app.billing_accounts b WHERE b.tenant_id = t.id)
        FROM app.tenants t WHERE t.id = i.tenant_id
    """)
    op.execute("ALTER TABLE app.platform_invoices ALTER COLUMN tenant_id DROP NOT NULL")
    op.execute("""
        ALTER TABLE app.platform_invoices
            DROP CONSTRAINT platform_invoices_tenant_id_fkey,
            ADD CONSTRAINT platform_invoices_tenant_id_fkey
                FOREIGN KEY (tenant_id) REFERENCES app.tenants (id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE FUNCTION app.platform_invoice_business() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            SELECT t.name INTO NEW.business_name FROM app.tenants t WHERE t.id = NEW.tenant_id;
            SELECT b.tax_id INTO NEW.business_tax_id
            FROM app.billing_accounts b WHERE b.tenant_id = NEW.tenant_id;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER platform_invoice_business BEFORE INSERT ON app.platform_invoices
        FOR EACH ROW EXECUTE FUNCTION app.platform_invoice_business()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER platform_invoice_business ON app.platform_invoices")
    op.execute("DROP FUNCTION app.platform_invoice_business()")
    op.execute("DELETE FROM app.platform_invoices WHERE tenant_id IS NULL")
    op.execute("""
        ALTER TABLE app.platform_invoices
            DROP CONSTRAINT platform_invoices_tenant_id_fkey,
            ADD CONSTRAINT platform_invoices_tenant_id_fkey
                FOREIGN KEY (tenant_id) REFERENCES app.tenants (id) ON DELETE CASCADE
    """)
    op.execute("ALTER TABLE app.platform_invoices ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("ALTER TABLE app.platform_invoices DROP COLUMN business_tax_id")
    op.execute("ALTER TABLE app.platform_invoices DROP COLUMN business_name")
    op.execute("DROP FUNCTION app.delete_my_account()")
    op.execute("ALTER TABLE app.users DROP COLUMN deleted_at")
    op.execute("DROP FUNCTION app.erase_client_traces(uuid)")
    op.execute("DROP FUNCTION app.client_app_ai_conversations(uuid)")
    op.execute("DROP FUNCTION app.client_announcement_deliveries(uuid)")
    op.execute("DROP FUNCTION app.data_export(uuid, uuid)")
    op.execute("DROP TABLE app.data_exports")
