"""Receipts: every successful payment gets a numbered receipt (per business, in order).

While payments are simulated the receipts are samples, marked as such; a real invoicing
provider (O2) will issue the legal documents and this table will hold their numbers and links.
Payments also record how they were paid.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.payments ADD COLUMN method text NOT NULL DEFAULT 'card'
            CHECK (method IN ('card', 'cash', 'transfer', 'other'))
    """)

    # The last receipt number of each business; the row lock orders concurrent payments.
    op.execute("""
        CREATE TABLE app.receipt_counters (
            tenant_id  uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            last       integer NOT NULL
        )
    """)
    op.execute("ALTER TABLE app.receipt_counters ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY receipt_counters_tenant ON app.receipt_counters FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.receipts (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            payment_id     uuid NOT NULL UNIQUE REFERENCES app.payments (id) ON DELETE CASCADE,
            client_id      uuid NOT NULL,
            entitlement_id uuid REFERENCES app.entitlements (id) ON DELETE SET NULL,
            number         integer NOT NULL,
            issued_at      timestamptz NOT NULL DEFAULT now(),
            business_name  text NOT NULL,
            client_name    text NOT NULL,
            client_email   text,
            description    text NOT NULL,
            amount         integer NOT NULL CHECK (amount >= 0),
            currency       char(3) NOT NULL,
            method         text NOT NULL,
            simulated      boolean NOT NULL,
            UNIQUE (tenant_id, number),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX receipts_client ON app.receipts (tenant_id, client_id)")
    op.execute("CREATE INDEX receipts_entitlement ON app.receipts (entitlement_id)")
    # Erasing a client replaces the name and email on their receipts.
    op.execute("GRANT SELECT, UPDATE (client_name, client_email) ON app.receipts TO app_api")
    op.execute("ALTER TABLE app.receipts ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY receipts_tenant ON app.receipts TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY receipts_client_select ON app.receipts FOR SELECT TO app_api
        USING (client_id = app.current_client_id())
    """)

    # Issued when the payment's transaction commits, so the plan it paid for is linked by then
    # (sales insert the payment first and link the entitlement right after).
    op.execute("""
        CREATE FUNCTION app.issue_receipt() RETURNS trigger
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
                   coalesce(e.name, ''), p.amount, p.currency, p.method,
                   p.provider = 'simulated'
            FROM app.payments p
            JOIN app.tenants t ON t.id = p.tenant_id
            JOIN app.clients c ON c.id = p.client_id
            LEFT JOIN app.entitlements e ON e.id = p.entitlement_id
            WHERE p.id = NEW.id AND p.status = 'succeeded';
            RETURN NULL;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.issue_receipt() FROM PUBLIC")
    op.execute("""
        CREATE CONSTRAINT TRIGGER payments_issue_receipt
        AFTER INSERT ON app.payments DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.issue_receipt()
    """)

    # Receipts for the payments made so far, numbered in the order they were made.
    op.execute("""
        WITH numbered AS (
            SELECT p.id, p.tenant_id,
                   1000 + row_number() OVER (PARTITION BY p.tenant_id ORDER BY p.created_at, p.id)
                       AS number
            FROM app.payments p WHERE p.status = 'succeeded'
        )
        INSERT INTO app.receipts
            (tenant_id, payment_id, client_id, entitlement_id, number, issued_at, business_name,
             client_name, client_email, description, amount, currency, method, simulated)
        SELECT p.tenant_id, p.id, p.client_id, p.entitlement_id, n.number, p.created_at, t.name,
               trim(c.first_name || ' ' || coalesce(c.last_name, '')), c.email,
               coalesce(e.name, ''), p.amount, p.currency, p.method, p.provider = 'simulated'
        FROM numbered n
        JOIN app.payments p ON p.id = n.id
        JOIN app.tenants t ON t.id = p.tenant_id
        JOIN app.clients c ON c.id = p.client_id
        LEFT JOIN app.entitlements e ON e.id = p.entitlement_id
    """)
    op.execute("""
        INSERT INTO app.receipt_counters (tenant_id, last)
        SELECT tenant_id, max(number) FROM app.receipts GROUP BY tenant_id
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER payments_issue_receipt ON app.payments")
    op.execute("DROP FUNCTION app.issue_receipt()")
    op.execute("DROP TABLE app.receipts")
    op.execute("DROP TABLE app.receipt_counters")
    op.execute("ALTER TABLE app.payments DROP COLUMN method")
