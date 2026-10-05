"""Actions MyBiz staff take on a business from the console: extend a trial, change its modules
and void (credit) an invoice. Each one needs `billing.manage`, is written to MyBiz's audit log
and to the business's own log, which its owner reads.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "platform_business_invoices(uuid)",
    "platform_extend_trial(uuid, integer)",
    "platform_set_modules(uuid, jsonb)",
    "platform_void_invoice(uuid, text)",
)


def upgrade() -> None:
    # Writes the action to both logs: MyBiz's console audit and the business's own.
    op.execute("""
        CREATE FUNCTION app.platform_record_action(
            p_tenant uuid, p_action text, p_details jsonb
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            PERFORM app.platform_audit_add(p_action, p_tenant, p_details);
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (p_tenant, 'platform', app.current_user_id(), p_action,
                    p_details || jsonb_build_object('email', v_email));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_business_invoices(p_tenant uuid)
        RETURNS TABLE (id uuid, number integer, period_start date, period_end date,
                       currency text, total integer, status text, issued_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT i.id, i.number, i.period_start, i.period_end, i.currency::text, i.total,
                   i.status, i.issued_at
            FROM app.platform_invoices i WHERE i.tenant_id = p_tenant
            ORDER BY i.number DESC LIMIT 60;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_extend_trial(p_tenant uuid, p_days integer)
        RETURNS timestamptz
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_until timestamptz;
        BEGIN
            IF p_days < 1 OR p_days > 180 THEN
                RAISE EXCEPTION 'invalid_days' USING ERRCODE = 'P0001';
            END IF;
            PERFORM app.platform_record_action(p_tenant, 'business.trial_extended',
                                               jsonb_build_object('days', p_days));
            UPDATE app.tenants
            SET trial_ends_at = greatest(trial_ends_at, now()) + make_interval(days => p_days)
            WHERE id = p_tenant
            RETURNING trial_ends_at INTO v_until;
            RETURN v_until;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_set_modules(p_tenant uuid, p_modules jsonb) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            PERFORM app.platform_record_action(p_tenant, 'business.modules_changed',
                                               jsonb_build_object('modules', p_modules));
            DELETE FROM app.tenant_modules WHERE tenant_id = p_tenant;
            INSERT INTO app.tenant_modules (tenant_id, module_key, quantity)
            SELECT p_tenant, key, (value #>> '{}')::int FROM jsonb_each(p_modules);
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_void_invoice(p_invoice uuid, p_reason text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid;
            v_status text;
        BEGIN
            SELECT tenant_id, status INTO v_tenant, v_status
            FROM app.platform_invoices WHERE id = p_invoice;
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            IF v_status = 'void' THEN
                RAISE EXCEPTION 'already_void' USING ERRCODE = 'P0001';
            END IF;
            PERFORM app.platform_record_action(
                v_tenant, 'business.invoice_voided',
                jsonb_build_object('invoice', p_invoice, 'reason', p_reason, 'was', v_status));
            UPDATE app.platform_invoices SET status = 'void' WHERE id = p_invoice;
        END
        $$
    """)
    for function in ("platform_record_action(uuid, text, jsonb)", *FUNCTIONS):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
    for function in FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP FUNCTION app.platform_record_action(uuid, text, jsonb)")
