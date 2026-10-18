"""Cancelling and pausing a MyBiz subscription (round 7, R33).

Expand step only: one table, two columns on `app.tenants`, and a handful of functions.

* `app.subscription_cancellations`: one row each time an owner cancels (or pauses) the MyBiz
  subscription: the reason they gave, when it ends, and the refund the policy gives (recorded
  only, no card is charged or refunded while payments are off). `resumed_at` is set when the
  owner takes it back. A first payment can be refunded once (unique `refund_invoice_id`).
* `tenants.pause_from` / `pause_until`: a pause keeps the data and the account read-only for up
  to three months at a flat monthly fee (the billing job writes that line).
* `app.effective_billing_state(tenants)`: the state the API enforces (a cancelled subscription
  that ended is suspended, a pause is read-only) so every query asks one place.
* `app.subscription_pause`: the owner starts or ends a pause.
* `app.platform_cancellations` and `app.platform_churn_months`: the console's churn view.

# contract: only the downgrade drops anything (the table, the columns and the functions); the
# upgrade adds them and touches nothing that exists, so the previous API version keeps working.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0134"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = "'too_expensive', 'missing_feature', 'not_using', 'switched', 'other'"
FUNCTIONS = (
    "platform_cancellations()",
    "platform_churn_months()",
    "subscription_pause(timestamptz, timestamptz)",
    "effective_billing_state(app.tenants)",
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.subscription_cancellations (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id           uuid REFERENCES app.users (id) ON DELETE SET NULL,
            outcome           text NOT NULL CHECK (outcome IN ('cancelled', 'paused')),
            reason            text CHECK (reason IN ({REASONS})),
            note              text CHECK (length(note) <= 1000),
            ends_at           timestamptz,
            refund_invoice_id uuid REFERENCES app.platform_invoices (id) ON DELETE SET NULL,
            refund_minor      integer NOT NULL DEFAULT 0 CHECK (refund_minor >= 0),
            currency          char(3) NOT NULL,
            created_at        timestamptz NOT NULL DEFAULT now(),
            resumed_at        timestamptz
        )
    """)
    op.execute("""
        CREATE INDEX subscription_cancellations_tenant
            ON app.subscription_cancellations (tenant_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX subscription_cancellations_user
            ON app.subscription_cancellations (user_id) WHERE user_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX subscription_cancellations_refund
            ON app.subscription_cancellations (refund_invoice_id)
            WHERE refund_invoice_id IS NOT NULL
    """)
    op.execute("""
        GRANT SELECT, INSERT, UPDATE (resumed_at) ON app.subscription_cancellations TO app_api
    """)
    op.execute("ALTER TABLE app.subscription_cancellations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY subscription_cancellations_tenant ON app.subscription_cancellations
        TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN pause_from  timestamptz,
            ADD COLUMN pause_until timestamptz
    """)

    op.execute("""
        CREATE FUNCTION app.effective_billing_state(t app.tenants) RETURNS text
        LANGUAGE sql STABLE SET search_path = '' AS $$
            SELECT CASE
                WHEN t.cancel_at <= now() THEN 'suspended'
                WHEN t.billing_state = 'active'
                     AND t.pause_from <= now() AND t.pause_until > now() THEN 'read_only'
                ELSE t.billing_state
            END
        $$
    """)
    op.execute("GRANT EXECUTE ON FUNCTION app.effective_billing_state(app.tenants) TO app_api")

    # The owner pauses the account (both dates) or ends the pause (both null).
    op.execute("""
        CREATE FUNCTION app.subscription_pause(p_from timestamptz, p_until timestamptz)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF app.current_tenant_id() IS NULL OR NOT EXISTS (
                SELECT 1 FROM app.tenant_members
                WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
                  AND role = 'owner'
            ) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.tenants SET pause_from = p_from, pause_until = p_until
            WHERE id = app.current_tenant_id();
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action)
            VALUES (app.current_tenant_id(), 'user', app.current_user_id(),
                    CASE WHEN p_from IS NULL THEN 'subscription.pause_ended'
                         ELSE 'subscription.paused' END);
        END
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app.subscription_pause(timestamptz, timestamptz) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.subscription_pause(timestamptz, timestamptz) TO app_api"
    )

    # Console: the last year's cancellations and pauses, newest first.
    op.execute("""
        CREATE FUNCTION app.platform_cancellations()
        RETURNS TABLE (id uuid, tenant_id uuid, name text, owner_email text, outcome text,
                       reason text, note text, created_at timestamptz, ends_at timestamptz,
                       refund_minor integer, currency text, resumed_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT c.id, c.tenant_id, t.name,
                   (SELECT u.email FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = c.tenant_id AND m.role = 'owner'
                    ORDER BY m.created_at LIMIT 1),
                   c.outcome, c.reason, c.note, c.created_at, c.ends_at, c.refund_minor,
                   c.currency::text, c.resumed_at
            FROM app.subscription_cancellations c
            JOIN app.tenants t ON t.id = c.tenant_id
            WHERE c.created_at >= now() - interval '12 months'
            ORDER BY c.created_at DESC
            LIMIT 500;
        END
        $$
    """)

    # Console: per month (UTC), how many cancelled, paused and took it back, against the
    # businesses that were past their trial at the month's start.
    op.execute("""
        CREATE FUNCTION app.platform_churn_months()
        RETURNS TABLE (month date, cancelled integer, paused integer, resumed integer,
                       paying_at_start integer)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT m.month::date,
                   (SELECT count(*)::integer FROM app.subscription_cancellations c
                    WHERE c.outcome = 'cancelled'
                      AND date_trunc('month', c.created_at AT TIME ZONE 'UTC') = m.month),
                   (SELECT count(*)::integer FROM app.subscription_cancellations c
                    WHERE c.outcome = 'paused'
                      AND date_trunc('month', c.created_at AT TIME ZONE 'UTC') = m.month),
                   (SELECT count(*)::integer FROM app.subscription_cancellations c
                    WHERE c.resumed_at IS NOT NULL
                      AND date_trunc('month', c.resumed_at AT TIME ZONE 'UTC') = m.month),
                   (SELECT count(*)::integer FROM app.tenants t
                    WHERE t.trial_ends_at < m.month AND t.created_at < m.month)
            FROM generate_series(
                     date_trunc('month', now() AT TIME ZONE 'UTC') - interval '11 months',
                     date_trunc('month', now() AT TIME ZONE 'UTC'),
                     interval '1 month') AS m(month)
            ORDER BY m.month;
        END
        $$
    """)
    for function in ("platform_cancellations()", "platform_churn_months()"):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("ALTER TABLE app.tenants DROP COLUMN pause_until, DROP COLUMN pause_from")
    op.execute("DROP TABLE app.subscription_cancellations")
