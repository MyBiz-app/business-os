"""Paying for a reservation (#41, decision X9): a court or room booked by the hour.

- A business chooses how reservations are paid: in the app when booking (the default) or at
  the venue (`tenants.resource_payment`).
- A payment can be for a reservation (`payments.booking_id`) and carries its own description,
  so its receipt says what was paid ("Padel court · Court 1 · 8 Oct 18:00"). Receipts use the
  plan's name as before, otherwise that description.
- app.pay_reservation lets a client pay for their own upcoming reservation (simulated until a
  payment provider is connected); staff record payments at the venue directly. Either way a
  reservation is paid at most once.

Revision ID: 0045
Revises: 0044
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _issue_receipt(description: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION app.issue_receipt() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_number integer;
        BEGIN
            IF EXISTS (SELECT 1 FROM app.receipts WHERE payment_id = NEW.id) THEN
                RETURN NULL;
            END IF;
            INSERT INTO app.receipt_counters AS c (tenant_id, last)
            VALUES (NEW.tenant_id, 1001)
            ON CONFLICT (tenant_id) DO UPDATE SET last = c.last + 1
            RETURNING last INTO v_number;
            INSERT INTO app.receipts
                (tenant_id, payment_id, client_id, entitlement_id, number, issued_at,
                 business_name, client_name, client_email, description, amount, currency, method,
                 simulated)
            SELECT p.tenant_id, p.id, p.client_id, p.entitlement_id, v_number, p.created_at,
                   t.name,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')), c.email,
                   {description}, p.amount, p.currency, p.method,
                   p.provider = 'simulated'
            FROM app.payments p
            JOIN app.tenants t ON t.id = p.tenant_id
            JOIN app.clients c ON c.id = p.client_id
            LEFT JOIN app.entitlements e ON e.id = p.entitlement_id
            WHERE p.id = NEW.id AND p.status = 'succeeded';
            RETURN NULL;
        END
        $$
    """


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants ADD COLUMN resource_payment text NOT NULL DEFAULT 'app'
            CHECK (resource_payment IN ('app', 'venue'))
    """)
    op.execute("GRANT UPDATE (resource_payment) ON app.tenants TO app_api")

    op.execute("""
        ALTER TABLE app.payments
            ADD COLUMN booking_id uuid REFERENCES app.bookings (id) ON DELETE SET NULL,
            ADD COLUMN description text CHECK (length(description) <= 200)
    """)
    # One successful payment per reservation booking.
    op.execute("""
        CREATE UNIQUE INDEX payments_booking_paid ON app.payments (booking_id)
        WHERE booking_id IS NOT NULL AND status = 'succeeded'
    """)
    op.execute(_issue_receipt("coalesce(e.name, p.description, '')"))

    op.execute("""
        CREATE FUNCTION app.pay_reservation(p_booking uuid, p_key text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_client uuid := app.current_client_id();
            v_row record;
            v_id uuid;
        BEGIN
            SELECT b.id, b.tenant_id, b.client_id, s.location_id, s.price_amount, s.price_currency,
                   sv.name || ' · ' || r.name || ' · '
                       || to_char(s.starts_at AT TIME ZONE t.time_zone, 'DD/MM HH24:MI')
                       AS description
            INTO v_row
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            JOIN app.rooms r ON r.id = s.room_id
            JOIN app.tenants t ON t.id = b.tenant_id
            WHERE b.id = p_booking AND b.client_id = v_client AND s.reserved
              AND b.status = 'booked' AND s.status = 'scheduled' AND s.starts_at > now();
            IF v_row.id IS NULL THEN
                RAISE EXCEPTION 'no such reservation' USING ERRCODE = 'P0002';
            END IF;
            SELECT id INTO v_id FROM app.payments
            WHERE booking_id = p_booking AND status = 'succeeded';
            IF v_id IS NOT NULL THEN
                RETURN v_id;  -- already paid: paying again changes nothing
            END IF;
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, method,
                 idempotency_key, created_by, booking_id, description, location_id)
            VALUES (v_row.tenant_id, v_row.client_id, coalesce(v_row.price_amount, 0),
                    coalesce(v_row.price_currency, 'ILS'), 'succeeded', 'simulated', 'card',
                    p_key, app.current_user_id(), p_booking, v_row.description,
                    v_row.location_id)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.pay_reservation(uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.pay_reservation(uuid, text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.pay_reservation(uuid, text)")
    op.execute(_issue_receipt("coalesce(e.name, '')"))
    op.execute("DROP INDEX app.payments_booking_paid")
    op.execute("ALTER TABLE app.payments DROP COLUMN description, DROP COLUMN booking_id")
    op.execute("REVOKE UPDATE (resource_payment) ON app.tenants FROM app_api")
    op.execute("ALTER TABLE app.tenants DROP COLUMN resource_payment")
