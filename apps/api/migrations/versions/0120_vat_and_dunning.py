"""MyBiz subscription billing: VAT, consecutive numbers, dunning, cancellation (go-live GL20).

* `vat_rates`: dated VAT rate per currency (18% for ILS from 2025-01-01); a currency with no row is
  billed without VAT.
* `platform_invoices` gets the amount before VAT, the rate used and the VAT. Old rows keep a null
  `subtotal` (they had no VAT); the code reads that as "the total is the subtotal".
* `platform_series`: a locked counter, so invoice numbers stay consecutive if a run rolls back.
* `dunning_settings` / `dunning_events`: when to remind, when the business turns read-only and
  when it is suspended (configurable and switchable off from the console); one row per email.
* `tenants.billing_state`, `billing_grace_until`, `cancel_at`, `billing_resumed_on`: the state the
  API enforces, a grace extension from the console, the end of a cancelled subscription (the
  business is kept) and the day a ended one was resumed (earlier months are not billed).

Revision ID: 0120
Revises: 0119
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0120"
down_revision: str | None = "0119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.vat_rates (
            currency   char(3) NOT NULL,
            valid_from date NOT NULL,
            rate_bp    integer NOT NULL CHECK (rate_bp BETWEEN 0 AND 5000),  -- 1800 = 18%
            PRIMARY KEY (currency, valid_from)
        )
    """)
    op.execute("INSERT INTO app.vat_rates VALUES ('ILS', '2025-01-01', 1800)")
    op.execute("GRANT SELECT ON app.vat_rates TO app_api")
    op.execute("ALTER TABLE app.vat_rates ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY vat_rates_read ON app.vat_rates FOR SELECT TO app_api USING (true)")

    op.execute("""
        ALTER TABLE app.platform_invoices
            ADD COLUMN subtotal    integer CHECK (subtotal >= 0),
            ADD COLUMN vat_rate_bp integer NOT NULL DEFAULT 0,
            ADD COLUMN vat_amount  integer NOT NULL DEFAULT 0
    """)
    op.execute("UPDATE app.platform_invoices SET subtotal = total")

    op.execute("""
        CREATE TABLE app.platform_series (
            kind text PRIMARY KEY,
            last integer NOT NULL
        )
    """)
    op.execute("ALTER TABLE app.platform_series ENABLE ROW LEVEL SECURITY")  # system only
    op.execute("""
        INSERT INTO app.platform_series
        SELECT 'invoice', greatest(coalesce(max(number), 0), 10000) FROM app.platform_invoices
    """)
    # Takes the next number inside the caller's transaction: the row lock orders concurrent runs
    # and a rollback gives the number back. The old sequence follows, so a rolled-back release
    # that still takes numbers from it does not collide.
    op.execute("""
        CREATE FUNCTION app.next_platform_invoice_number() RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_number integer;
        BEGIN
            UPDATE app.platform_series SET last = last + 1 WHERE kind = 'invoice'
            RETURNING last INTO v_number;
            PERFORM setval('app.platform_invoice_number', v_number);
            RETURN v_number;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.next_platform_invoice_number() FROM PUBLIC")

    op.execute("""
        CREATE TABLE app.dunning_settings (
            singleton            boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            enabled              boolean NOT NULL DEFAULT true,
            reminder_days        integer[] NOT NULL DEFAULT '{0,3,7}',
            read_only_after_days integer NOT NULL DEFAULT 14 CHECK (read_only_after_days > 0),
            suspend_after_days   integer NOT NULL DEFAULT 30,
            updated_at           timestamptz NOT NULL DEFAULT now(),
            CHECK (suspend_after_days > read_only_after_days)
        )
    """)
    op.execute("INSERT INTO app.dunning_settings DEFAULT VALUES")
    op.execute("GRANT SELECT ON app.dunning_settings TO app_api")
    op.execute("ALTER TABLE app.dunning_settings ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY dunning_settings_read ON app.dunning_settings FOR SELECT TO app_api
        USING (true)
    """)

    op.execute("""
        CREATE TABLE app.dunning_events (
            invoice_id uuid NOT NULL REFERENCES app.platform_invoices (id) ON DELETE CASCADE,
            stage      integer NOT NULL,  -- the reminder day it was sent for
            emailed    boolean NOT NULL DEFAULT false,
            sent_at    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (invoice_id, stage)
        )
    """)

    op.execute("ALTER TABLE app.dunning_events ENABLE ROW LEVEL SECURITY")  # system only
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN billing_state text NOT NULL DEFAULT 'active'
                CHECK (billing_state IN ('active', 'read_only', 'suspended')),
            ADD COLUMN billing_grace_until timestamptz,
            ADD COLUMN cancel_at timestamptz,
            ADD COLUMN billing_resumed_on date
    """)

    # Paying the last overdue invoice lifts the restriction at once.
    op.execute("""
        CREATE OR REPLACE FUNCTION app.pay_platform_invoice(p_invoice uuid) RETURNS void
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
            IF NOT EXISTS (
                SELECT 1 FROM app.platform_invoices WHERE tenant_id = v_tenant AND status = 'open'
            ) THEN
                UPDATE app.tenants SET billing_state = 'active' WHERE id = v_tenant;
            END IF;
        END
        $$
    """)

    # The owner ends the subscription at `p_at` (or takes the cancellation back with null).
    op.execute("""
        CREATE FUNCTION app.set_subscription_cancel(p_at timestamptz) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF app.current_tenant_id() IS NULL OR NOT EXISTS (
                SELECT 1 FROM app.tenant_members
                WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
                  AND role = 'owner'
            ) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            -- Resuming after the subscription ended: the months in between are not billed.
            UPDATE app.tenants
            SET billing_resumed_on = CASE WHEN p_at IS NULL AND cancel_at <= now()
                                          THEN current_date ELSE billing_resumed_on END,
                cancel_at = p_at
            WHERE id = app.current_tenant_id();
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action)
            VALUES (app.current_tenant_id(), 'user', app.current_user_id(),
                    CASE WHEN p_at IS NULL THEN 'subscription.resumed'
                         ELSE 'subscription.cancelled' END);
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.set_subscription_cancel(timestamptz) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.set_subscription_cancel(timestamptz) TO app_api")

    # Console: the businesses with an unpaid invoice, the oldest first.
    op.execute("""
        CREATE FUNCTION app.platform_overdue_businesses()
        RETURNS TABLE (tenant_id uuid, name text, owner_email text, currency text,
                       open_invoices bigint, open_amount bigint, oldest_issued_at timestamptz,
                       billing_state text, grace_until timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT t.id, t.name, (SELECT u.email FROM app.tenant_members m
                                  JOIN app.users u ON u.id = m.user_id
                                  WHERE m.tenant_id = t.id AND m.role = 'owner'
                                  ORDER BY m.created_at LIMIT 1),
                   i.currency::text, count(*), sum(i.total)::bigint, min(i.issued_at),
                   t.billing_state, t.billing_grace_until
            FROM app.platform_invoices i JOIN app.tenants t ON t.id = i.tenant_id
            WHERE i.status = 'open' AND t.closed_at IS NULL
            GROUP BY t.id, t.name, i.currency, t.billing_state, t.billing_grace_until
            ORDER BY min(i.issued_at);
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_overdue_businesses() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_overdue_businesses() TO app_api")

    # Console: lifts the restriction and holds off the next one for `p_days` days.
    op.execute("""
        CREATE FUNCTION app.platform_extend_grace(p_tenant uuid, p_days integer) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_until timestamptz := now() + make_interval(days => p_days);
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.tenants SET billing_grace_until = v_until, billing_state = 'active'
            WHERE id = p_tenant;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            PERFORM app.platform_record_action(
                p_tenant, 'billing.grace_extended',
                jsonb_build_object('days', p_days, 'until', v_until));
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_extend_grace(uuid, integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_extend_grace(uuid, integer) TO app_api")

    op.execute("""
        CREATE FUNCTION app.platform_dunning_update(
            p_enabled boolean, p_reminder_days integer[], p_read_only integer, p_suspend integer
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.dunning_settings
            SET enabled = p_enabled, reminder_days = p_reminder_days,
                read_only_after_days = p_read_only, suspend_after_days = p_suspend,
                updated_at = now();
            PERFORM app.platform_audit_add(
                'billing.dunning_updated', NULL,
                jsonb_build_object('enabled', p_enabled, 'reminder_days', p_reminder_days,
                                   'read_only_after_days', p_read_only,
                                   'suspend_after_days', p_suspend));
        END
        $$
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION app.platform_dunning_update(
            boolean, integer[], integer, integer) FROM PUBLIC
    """)
    op.execute("""
        GRANT EXECUTE ON FUNCTION app.platform_dunning_update(
            boolean, integer[], integer, integer) TO app_api
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_dunning_update(boolean, integer[], integer, integer)")
    op.execute("DROP FUNCTION app.platform_extend_grace(uuid, integer)")
    op.execute("DROP FUNCTION app.platform_overdue_businesses()")
    op.execute("DROP FUNCTION app.set_subscription_cancel(timestamptz)")
    op.execute("""
        CREATE OR REPLACE FUNCTION app.pay_platform_invoice(p_invoice uuid) RETURNS void
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
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN billing_resumed_on, DROP COLUMN cancel_at,
            DROP COLUMN billing_grace_until, DROP COLUMN billing_state
    """)
    op.execute("DROP TABLE app.dunning_events")
    op.execute("DROP TABLE app.dunning_settings")
    op.execute("DROP FUNCTION app.next_platform_invoice_number()")
    op.execute("DROP TABLE app.platform_series")
    op.execute("""
        ALTER TABLE app.platform_invoices
            DROP COLUMN vat_amount, DROP COLUMN vat_rate_bp, DROP COLUMN subtotal
    """)
    op.execute("DROP TABLE app.vat_rates")
