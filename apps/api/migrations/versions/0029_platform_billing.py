"""Platform billing (MyBiz → business), simulated: a free trial, then a monthly invoice for the
modules the business has on, charged to a test payment method.

Invoices are written by the `bill-businesses` job (system connection); businesses only read
them. Paying an open invoice by hand goes through app.pay_platform_invoice. No real card data is
ever collected: the payment method is a test card the owner adds with one click. A payment
provider (O1) will replace the simulation.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIAL = "interval '14 days'"


def upgrade() -> None:
    op.execute("ALTER TABLE app.tenants ADD COLUMN trial_ends_at timestamptz")
    op.execute(f"UPDATE app.tenants SET trial_ends_at = created_at + {TRIAL}")
    op.execute(f"""
        ALTER TABLE app.tenants
            ALTER COLUMN trial_ends_at SET DEFAULT now() + {TRIAL},
            ALTER COLUMN trial_ends_at SET NOT NULL
    """)

    op.execute("""
        CREATE TABLE app.billing_accounts (
            tenant_id      uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            billing_name   text CHECK (length(billing_name) <= 160),
            billing_email  text CHECK (length(billing_email) <= 254),
            tax_id         text CHECK (length(tax_id) <= 40),
            card_brand     text CHECK (card_brand IN ('visa', 'mastercard', 'amex')),
            card_last4     char(4),
            card_exp       char(5),  -- MM/YY
            card_simulated boolean NOT NULL DEFAULT true,
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.billing_accounts TO app_api")
    op.execute("ALTER TABLE app.billing_accounts ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY billing_accounts_tenant ON app.billing_accounts TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("CREATE SEQUENCE app.platform_invoice_number START 10001")
    op.execute("""
        CREATE TABLE app.platform_invoices (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            number          integer NOT NULL UNIQUE
                                DEFAULT nextval('app.platform_invoice_number'),
            period_start    date NOT NULL,
            period_end      date NOT NULL CHECK (period_end >= period_start),
            currency        char(3) NOT NULL,
            active_clients  integer NOT NULL,
            lines           jsonb NOT NULL,  -- [{"key": "core" | module, "quantity", "amount"}]
            total           integer NOT NULL CHECK (total >= 0),
            status          text NOT NULL CHECK (status IN ('open', 'paid', 'void')),
            issued_at       timestamptz NOT NULL DEFAULT now(),
            paid_at         timestamptz,
            card_last4      char(4),
            simulated       boolean NOT NULL DEFAULT true,
            UNIQUE (tenant_id, period_start)
        )
    """)
    op.execute(
        "CREATE INDEX platform_invoices_tenant ON app.platform_invoices (tenant_id, period_start)"
    )
    op.execute("GRANT SELECT ON app.platform_invoices TO app_api")
    op.execute("ALTER TABLE app.platform_invoices ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY platform_invoices_tenant ON app.platform_invoices FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)

    # The owner pays an open invoice with the business's (test) card.
    op.execute("""
        CREATE FUNCTION app.pay_platform_invoice(p_invoice uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid := app.current_tenant_id();
            v_last4 char(4);
        BEGIN
            SELECT card_last4 INTO v_last4 FROM app.billing_accounts WHERE tenant_id = v_tenant;
            IF v_last4 IS NULL THEN
                RAISE EXCEPTION 'no payment method' USING ERRCODE = 'P0001';
            END IF;
            UPDATE app.platform_invoices SET status = 'paid', paid_at = now(), card_last4 = v_last4
            WHERE id = p_invoice AND tenant_id = v_tenant AND status = 'open';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'no open invoice' USING ERRCODE = 'P0002';
            END IF;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.pay_platform_invoice(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.pay_platform_invoice(uuid) TO app_api")

    # Platform admins: billed revenue per month and currency.
    op.execute("""
        CREATE FUNCTION app.platform_billing_summary()
        RETURNS TABLE (month date, currency char(3), invoices bigint, paid bigint, open bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT date_trunc('month', i.period_start)::date, i.currency, count(*),
                   coalesce(sum(i.total) FILTER (WHERE i.status = 'paid'), 0)::bigint,
                   coalesce(sum(i.total) FILTER (WHERE i.status = 'open'), 0)::bigint
            FROM app.platform_invoices i
            WHERE i.period_start > now() - interval '12 months'
            GROUP BY 1, 2 ORDER BY 1 DESC, 2;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_billing_summary() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_billing_summary() TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_billing_summary()")
    op.execute("DROP FUNCTION app.pay_platform_invoice(uuid)")
    op.execute("DROP TABLE app.platform_invoices")
    op.execute("DROP SEQUENCE app.platform_invoice_number")
    op.execute("DROP TABLE app.billing_accounts")
    op.execute("ALTER TABLE app.tenants DROP COLUMN trial_ends_at")
