"""Client checkouts: a client buys a plan in the app.

A checkout records what the client is buying (plan and price at that moment) and its payment
state. Completing it records the payment and creates the client's plan exactly once
(app.complete_checkout). Until a payment provider is connected (decision O1), checkouts use
the "simulated" provider and the client confirms a test payment; real providers will
complete checkouts from their webhook, on a system connection.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN online_sales boolean NOT NULL DEFAULT false")
    op.execute("""
        CREATE TABLE app.checkouts (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id       uuid NOT NULL,
            plan_id         uuid NOT NULL,
            amount          integer NOT NULL CHECK (amount >= 0),
            currency        char(3) NOT NULL,
            provider        text NOT NULL,
            provider_ref    text,
            status          text NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'paid', 'cancelled', 'failed')),
            entitlement_id  uuid,
            created_at      timestamptz NOT NULL DEFAULT now(),
            completed_at    timestamptz,
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, plan_id) REFERENCES app.plans (tenant_id, id),
            FOREIGN KEY (tenant_id, entitlement_id) REFERENCES app.entitlements (tenant_id, id)
        )
    """)
    op.execute(
        "CREATE INDEX checkouts_client_idx ON app.checkouts (tenant_id, client_id, created_at)"
    )
    op.execute("GRANT SELECT, INSERT ON app.checkouts TO app_api")
    op.execute("ALTER TABLE app.checkouts ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY checkouts_tenant ON app.checkouts FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY checkouts_client_select ON app.checkouts FOR SELECT TO app_api
        USING (client_id = app.current_client_id())
    """)
    # Clients start their own checkouts; only app.complete_checkout changes them.
    op.execute("""
        CREATE POLICY checkouts_client_insert ON app.checkouts FOR INSERT TO app_api
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id()
                    AND status = 'pending')
    """)
    op.execute("""
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
    """)
    op.execute("REVOKE ALL ON FUNCTION app.complete_checkout(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.complete_checkout(uuid) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.complete_checkout(uuid)")
    op.execute("DROP TABLE app.checkouts")
    op.execute("ALTER TABLE app.tenants DROP COLUMN online_sales")
