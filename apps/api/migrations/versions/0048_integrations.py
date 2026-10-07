"""Integrations (decision X13): swappable providers for payments, invoicing and messaging.

- A business can connect its own provider per capability (`app.tenant_integrations`): the
  provider's name, its plain settings and its secrets, encrypted by the API with the platform's
  key (the database never sees them in clear). Without one, the platform's default applies.
- Receipts carry their legal document from the business's invoicing provider
  (`document_status`: pending → issued / internal / failed, its number and link). Receipts
  issued before this keep MyBiz's receipt as the document (`internal`).
- Messages are an outbox: queued until the business's messaging provider sends them; the
  provider's id, error and attempts are kept.
- A checkout can have a hosted payment page (`checkouts.pay_url`) and be completed by the
  provider's verified webhook (app.complete_provider_checkout), not only by the simulated
  "pay" button (app.complete_checkout). Both share app.finish_checkout.

Revision ID: 0048
Revises: 0047
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FINISH = """
    CREATE FUNCTION app.finish_checkout(p_checkout_id uuid, p_ref text) RETURNS uuid
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v app.checkouts;
        v_payment uuid;
        v_entitlement uuid;
    BEGIN
        SELECT * INTO v FROM app.checkouts WHERE id = p_checkout_id FOR UPDATE;
        IF v.status = 'paid' THEN
            RETURN v.entitlement_id;
        END IF;
        IF v.status <> 'pending' THEN
            RAISE EXCEPTION 'checkout is %', v.status USING ERRCODE = 'P0001';
        END IF;
        INSERT INTO app.payments
            (tenant_id, client_id, amount, currency, status, provider, provider_ref,
             idempotency_key)
        VALUES (v.tenant_id, v.client_id, v.amount, v.currency, 'succeeded', v.provider,
                coalesce(p_ref, v.provider_ref), 'checkout:' || v.id)
        RETURNING id INTO v_payment;
        INSERT INTO app.entitlements
            (tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
             price_amount, price_currency)
        SELECT p.tenant_id, v.client_id, p.id, p.name, p.kind, p.credits, today.value,
               today.value + p.validity_days - 1, v.amount, v.currency
        FROM app.plans p
        JOIN app.tenants t ON t.id = p.tenant_id
        CROSS JOIN LATERAL (SELECT (now() AT TIME ZONE t.time_zone)::date AS value) today
        WHERE p.id = v.plan_id
        RETURNING id INTO v_entitlement;
        UPDATE app.payments SET entitlement_id = v_entitlement WHERE id = v_payment;
        UPDATE app.checkouts
        SET status = 'paid', completed_at = now(), entitlement_id = v_entitlement,
            provider_ref = coalesce(p_ref, provider_ref)
        WHERE id = v.id;
        RETURN v_entitlement;
    END
    $$
"""

COMPLETE_SIMULATED = """
    CREATE OR REPLACE FUNCTION app.complete_checkout(p_checkout_id uuid) RETURNS uuid
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v app.checkouts;
    BEGIN
        SELECT * INTO v FROM app.checkouts WHERE id = p_checkout_id;
        -- Through the API, a client completes only their own simulated checkout.
        IF v.id IS NULL OR v.client_id IS DISTINCT FROM app.current_client_id()
           OR v.provider <> 'simulated' THEN
            RAISE EXCEPTION 'checkout not found' USING ERRCODE = 'P0002';
        END IF;
        RETURN app.finish_checkout(v.id, NULL);
    END
    $$
"""

COMPLETE_PROVIDER = """
    CREATE FUNCTION app.complete_provider_checkout(
        p_checkout_id uuid, p_provider text, p_ref text, p_amount integer, p_currency text
    ) RETURNS uuid
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v app.checkouts;
    BEGIN
        -- Called after the API verified the provider's webhook signature: the checkout must
        -- be that provider's, for that amount.
        SELECT * INTO v FROM app.checkouts WHERE id = p_checkout_id;
        IF v.id IS NULL OR v.provider <> p_provider OR v.provider = 'simulated' THEN
            RAISE EXCEPTION 'checkout not found' USING ERRCODE = 'P0002';
        END IF;
        IF v.amount <> p_amount OR v.currency <> p_currency THEN
            RAISE EXCEPTION 'amount does not match' USING ERRCODE = '22023';
        END IF;
        RETURN app.finish_checkout(v.id, p_ref);
    END
    $$
"""

ORIGINAL_COMPLETE = """
        CREATE FUNCTION app.complete_checkout(p_checkout_id uuid) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v app.checkouts;
            v_payment uuid;
            v_entitlement uuid;
        BEGIN
            SELECT * INTO v FROM app.checkouts WHERE id = p_checkout_id FOR UPDATE;
            -- Through the API, a client completes only their own simulated checkout.
            IF v.id IS NULL OR v.client_id IS DISTINCT FROM app.current_client_id()
               OR v.provider <> 'simulated' THEN
                RAISE EXCEPTION 'checkout not found' USING ERRCODE = 'P0002';
            END IF;
            IF v.status = 'paid' THEN
                RETURN v.entitlement_id;
            END IF;
            IF v.status <> 'pending' THEN
                RAISE EXCEPTION 'checkout is %', v.status USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, provider_ref,
                 idempotency_key)
            VALUES (v.tenant_id, v.client_id, v.amount, v.currency, 'succeeded', v.provider,
                    v.provider_ref, 'checkout:' || v.id)
            RETURNING id INTO v_payment;
            INSERT INTO app.entitlements
                (tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
                 price_amount, price_currency)
            SELECT p.tenant_id, v.client_id, p.id, p.name, p.kind, p.credits, today.value,
                   today.value + p.validity_days - 1, v.amount, v.currency
            FROM app.plans p
            JOIN app.tenants t ON t.id = p.tenant_id
            CROSS JOIN LATERAL (SELECT (now() AT TIME ZONE t.time_zone)::date AS value) today
            WHERE p.id = v.plan_id
            RETURNING id INTO v_entitlement;
            UPDATE app.payments SET entitlement_id = v_entitlement WHERE id = v_payment;
            UPDATE app.checkouts
            SET status = 'paid', completed_at = now(), entitlement_id = v_entitlement
            WHERE id = v.id;
            RETURN v_entitlement;
        END
        $$
"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.tenant_integrations (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            capability    text NOT NULL
                          CHECK (capability IN ('payments', 'invoicing', 'messaging')),
            provider      text NOT NULL CHECK (provider ~ '^[a-z][a-z0-9_]{1,40}$'),
            settings      jsonb NOT NULL DEFAULT '{}',
            secrets       bytea,
            active        boolean NOT NULL DEFAULT true,
            connected_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            connected_at  timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, capability)
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.tenant_integrations TO app_api")
    op.execute("ALTER TABLE app.tenant_integrations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_integrations_tenant ON app.tenant_integrations TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # The webhook of a provider and the system jobs read a business's connection without a
    # signed-in member: through this function only.
    op.execute("""
        CREATE FUNCTION app.tenant_integration(p_tenant uuid, p_capability text)
        RETURNS TABLE (provider text, settings jsonb, secrets bytea)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT i.provider, i.settings, i.secrets FROM app.tenant_integrations i
            WHERE i.tenant_id = p_tenant AND i.capability = p_capability AND i.active
        $$
    """)
    # The MyBiz console: how many businesses connected each provider (no business details).
    op.execute("""
        CREATE FUNCTION app.integration_counts()
        RETURNS TABLE (capability text, provider text, businesses integer)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT i.capability, i.provider, count(*)::integer FROM app.tenant_integrations i
            WHERE i.active AND app.is_platform_admin()
            GROUP BY i.capability, i.provider
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.integration_counts() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.integration_counts() TO app_api")
    op.execute("REVOKE ALL ON FUNCTION app.tenant_integration(uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.tenant_integration(uuid, text) TO app_api")

    op.execute("""
        ALTER TABLE app.receipts
            ADD COLUMN document_status text NOT NULL DEFAULT 'internal'
                CHECK (document_status IN ('pending', 'issued', 'internal', 'failed')),
            ADD COLUMN document_provider text,
            ADD COLUMN document_number text CHECK (length(document_number) <= 60),
            ADD COLUMN document_url text CHECK (length(document_url) <= 1000),
            ADD COLUMN document_error text CHECK (length(document_error) <= 500),
            ADD COLUMN document_attempts integer NOT NULL DEFAULT 0
    """)
    # From now on a new receipt waits for the business's invoicing provider.
    op.execute("ALTER TABLE app.receipts ALTER COLUMN document_status SET DEFAULT 'pending'")
    op.execute("""
        CREATE INDEX receipts_document_pending ON app.receipts (issued_at)
        WHERE document_status = 'pending'
    """)

    op.execute("""
        ALTER TABLE app.messages
            ADD COLUMN provider text,
            ADD COLUMN provider_ref text CHECK (length(provider_ref) <= 200),
            ADD COLUMN error text CHECK (length(error) <= 500),
            ADD COLUMN attempts integer NOT NULL DEFAULT 0,
            ADD COLUMN sent_at timestamptz
    """)
    op.execute("UPDATE app.messages SET sent_at = created_at WHERE status = 'sent'")
    op.execute("CREATE INDEX messages_queued ON app.messages (created_at) WHERE status = 'queued'")

    op.execute("ALTER TABLE app.checkouts ADD COLUMN pay_url text CHECK (length(pay_url) <= 2000)")
    op.execute("GRANT UPDATE (provider_ref, pay_url) ON app.checkouts TO app_api")
    # A client asks for the payment page of their own pending checkout.
    op.execute("""
        CREATE POLICY checkouts_client_pay_page ON app.checkouts FOR UPDATE TO app_api
        USING (client_id = app.current_client_id() AND status = 'pending')
        WITH CHECK (client_id = app.current_client_id() AND status = 'pending')
    """)
    op.execute(FINISH)
    op.execute("REVOKE ALL ON FUNCTION app.finish_checkout(uuid, text) FROM PUBLIC")
    op.execute(COMPLETE_SIMULATED)
    op.execute(COMPLETE_PROVIDER)
    signature = "app.complete_provider_checkout(uuid, text, text, integer, text)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.complete_provider_checkout(uuid, text, text, integer, text)")
    op.execute("DROP FUNCTION app.complete_checkout(uuid)")
    op.execute("DROP FUNCTION app.finish_checkout(uuid, text)")
    op.execute(ORIGINAL_COMPLETE)
    op.execute("REVOKE ALL ON FUNCTION app.complete_checkout(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.complete_checkout(uuid) TO app_api")
    op.execute("DROP POLICY checkouts_client_pay_page ON app.checkouts")
    op.execute("REVOKE UPDATE (provider_ref, pay_url) ON app.checkouts FROM app_api")
    op.execute("ALTER TABLE app.checkouts DROP COLUMN pay_url")
    op.execute("DROP INDEX app.messages_queued")
    op.execute("""
        ALTER TABLE app.messages DROP COLUMN sent_at, DROP COLUMN attempts, DROP COLUMN error,
            DROP COLUMN provider_ref, DROP COLUMN provider
    """)
    op.execute("DROP INDEX app.receipts_document_pending")
    op.execute("""
        ALTER TABLE app.receipts DROP COLUMN document_attempts, DROP COLUMN document_error,
            DROP COLUMN document_url, DROP COLUMN document_number,
            DROP COLUMN document_provider, DROP COLUMN document_status
    """)
    op.execute("DROP FUNCTION app.integration_counts()")
    op.execute("DROP FUNCTION app.tenant_integration(uuid, text)")
    op.execute("DROP TABLE app.tenant_integrations")
