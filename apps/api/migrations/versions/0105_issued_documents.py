"""Issued documents and their number series (round 6, T2).

A business issues tax invoice-receipts, tax invoices, credit notes, quotes and transaction
invoices (receipts keep their own counter, migration 0025). Each kind has its own running
number per business (`document_series`), taken inside the issuing transaction by
`app.next_document_number`, so a rolled-back issue leaves no hole. An issued document is stored
as the PDF that was produced (`content`, with its sha256) and is never changed or deleted by the
API: a mistake is corrected with a credit note. Payslips are not part of this (plain, T1 rules).

Revision ID: 0105
Revises: 0111
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0105"
down_revision: str | None = "0111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = ("tax_invoice_receipt", "tax_invoice", "credit_note", "quote", "transaction_invoice")
FIRST_NUMBER = 1001  # the same starting point the receipts use


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.document_series (
            tenant_id uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            kind      text NOT NULL CHECK (kind IN {KINDS!r}),
            last      integer NOT NULL,
            PRIMARY KEY (tenant_id, kind)
        )
    """)
    op.execute("ALTER TABLE app.document_series ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY document_series_tenant ON app.document_series FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)
    op.execute("GRANT SELECT ON app.document_series TO app_api")

    # The only way to move a series on. The row lock orders concurrent issues; the number is
    # taken in the caller's transaction, so it is released with it if the issue fails.
    op.execute(f"""
        CREATE FUNCTION app.next_document_number(p_kind text) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_number integer;
        BEGIN
            IF app.current_tenant_id() IS NULL THEN
                RAISE EXCEPTION 'no business selected';
            END IF;
            INSERT INTO app.document_series AS s (tenant_id, kind, last)
            VALUES (app.current_tenant_id(), p_kind, {FIRST_NUMBER})
            ON CONFLICT (tenant_id, kind) DO UPDATE SET last = s.last + 1
            RETURNING s.last INTO v_number;
            RETURN v_number;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.next_document_number(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.next_document_number(text) TO app_api")

    op.execute(f"""
        CREATE TABLE app.issued_documents (
            id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id             uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            kind                  text NOT NULL CHECK (kind IN {KINDS!r}),
            number                integer NOT NULL,
            issued_at             timestamptz NOT NULL DEFAULT now(),
            language              text NOT NULL CHECK (language IN ('he', 'en')),
            client_id             uuid,
            client_name           text NOT NULL CHECK (length(client_name) BETWEEN 1 AND 200),
            client_email          text,
            client_tax_id         text CHECK (length(client_tax_id) <= 20),
            currency              char(3) NOT NULL,
            lines                 jsonb NOT NULL,
            vat_rate_bp           integer NOT NULL CHECK (vat_rate_bp BETWEEN 0 AND 10000),
            net                   integer NOT NULL CHECK (net >= 0),
            vat                   integer NOT NULL CHECK (vat >= 0),
            total                 integer NOT NULL CHECK (total >= 0),
            payment_method        text
                                  CHECK (payment_method IN ('card', 'cash', 'transfer', 'other')),
            due_date              date,
            valid_until           date,
            payment_terms         text CHECK (length(payment_terms) <= 300),
            notes                 text CHECK (length(notes) <= 1000),
            reference_id          uuid REFERENCES app.issued_documents (id),
            allocation_required   boolean NOT NULL DEFAULT false,
            allocation_number     text CHECK (length(allocation_number) <= 40),
            content               bytea NOT NULL,
            content_hash          text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            issued_by             uuid,
            UNIQUE (tenant_id, kind, number),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE SET NULL (client_id),
            CHECK ((kind = 'credit_note') = (reference_id IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE INDEX issued_documents_list ON app.issued_documents (tenant_id, issued_at DESC)"
    )
    op.execute(
        "CREATE INDEX issued_documents_client ON app.issued_documents (tenant_id, client_id)"
    )
    op.execute("CREATE INDEX issued_documents_reference ON app.issued_documents (reference_id)")
    # Insert and read only: an issued document is never edited or removed through the API.
    op.execute("GRANT SELECT, INSERT ON app.issued_documents TO app_api")
    op.execute("ALTER TABLE app.issued_documents ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY issued_documents_select ON app.issued_documents FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY issued_documents_insert ON app.issued_documents FOR INSERT TO app_api
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.issued_documents")
    op.execute("DROP FUNCTION app.next_document_number(text)")
    op.execute("DROP TABLE app.document_series")
