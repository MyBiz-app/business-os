"""Documents, retainers and time-based billing (#45, decision X14).

- Client documents (`app.client_documents`): files on the client's card. The bytes are kept by
  the storage provider (X13): the built-in `database` provider keeps them in `content`; another
  provider keeps them elsewhere under `storage_key`. Staff choose what the client sees
  (`shared`); clients upload their own papers and see them; a document can ask for the
  client's signature, given by writing their name (app.sign_document).
- Time entries (`app.time_entries`): who worked for which client, the day, minutes, what was
  done, billable or not, and the bill that billed them (never billed twice).
- Retainers (`app.retainers`): a client's monthly fee, the minutes it includes and the hourly
  rate beyond them.
- Bills are quotes of kind `bill` (`quotes.kind`), for a period, already accepted with the
  whole amount due, paid by the same private link.

Revision ID: 0050
Revises: 0049
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_FILE = 10 * 1024 * 1024

QUOTE_BY_TOKEN = """
        CREATE OR REPLACE FUNCTION app.quote_by_token(p_token text) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT jsonb_build_object(
                'id', q.id, 'number', q.number, 'kind', q.kind,
                'period_start', q.period_start, 'period_end', q.period_end,
                'title', q.title, 'status', q.status,
                'currency', q.currency, 'deposit_percent', q.deposit_percent,
                'valid_until', q.valid_until, 'event_starts_at', q.event_starts_at,
                'event_place', q.event_place, 'notes', q.notes, 'sent_at', q.sent_at,
                'accepted_at', q.accepted_at, 'accepted_name', q.accepted_name,
                'declined_at', q.declined_at,
                'total', app.quote_total(q.id), 'paid', app.quote_paid(q.id),
                'business_name', t.name, 'business_locale', t.locale,
                'business_color', t.primary_color, 'time_zone', t.time_zone,
                'client_name', trim(c.first_name || ' ' || coalesce(c.last_name, '')),
                'lines', coalesce((
                    SELECT jsonb_agg(jsonb_build_object(
                        'description', l.description, 'quantity', l.quantity,
                        'unit_price', l.unit_price
                    ) ORDER BY l.position)
                    FROM app.quote_lines l WHERE l.quote_id = q.id
                ), '[]'::jsonb)
            )
            FROM app.quotes q
            JOIN app.tenants t ON t.id = q.tenant_id
            JOIN app.clients c ON c.id = q.client_id
            WHERE q.token = p_token AND q.status <> 'draft'
        $$
"""
OLD_QUOTE_BY_TOKEN = """
        CREATE OR REPLACE FUNCTION app.quote_by_token(p_token text) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT jsonb_build_object(
                'id', q.id, 'number', q.number, 'title', q.title, 'status', q.status,
                'currency', q.currency, 'deposit_percent', q.deposit_percent,
                'valid_until', q.valid_until, 'event_starts_at', q.event_starts_at,
                'event_place', q.event_place, 'notes', q.notes, 'sent_at', q.sent_at,
                'accepted_at', q.accepted_at, 'accepted_name', q.accepted_name,
                'declined_at', q.declined_at,
                'total', app.quote_total(q.id), 'paid', app.quote_paid(q.id),
                'business_name', t.name, 'business_locale', t.locale,
                'business_color', t.primary_color, 'time_zone', t.time_zone,
                'client_name', trim(c.first_name || ' ' || coalesce(c.last_name, '')),
                'lines', coalesce((
                    SELECT jsonb_agg(jsonb_build_object(
                        'description', l.description, 'quantity', l.quantity,
                        'unit_price', l.unit_price
                    ) ORDER BY l.position)
                    FROM app.quote_lines l WHERE l.quote_id = q.id
                ), '[]'::jsonb)
            )
            FROM app.quotes q
            JOIN app.tenants t ON t.id = q.tenant_id
            JOIN app.clients c ON c.id = q.client_id
            WHERE q.token = p_token AND q.status <> 'draft'
        $$
"""


def _tenant_policy(table: str) -> None:
    op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table}_tenant ON app.{table} TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.client_documents (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id           uuid NOT NULL,
            name                text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
            kind                text NOT NULL DEFAULT 'other'
                                CHECK (kind IN ('contract', 'report', 'client_file', 'other')),
            content_type        text NOT NULL CHECK (length(content_type) <= 120),
            size                integer NOT NULL CHECK (size BETWEEN 1 AND {MAX_FILE}),
            content             bytea,
            storage_key         text CHECK (length(storage_key) <= 500),
            shared              boolean NOT NULL DEFAULT false,
            uploaded_by_client  boolean NOT NULL DEFAULT false,
            sign_requested      boolean NOT NULL DEFAULT false,
            signed_at           timestamptz,
            signed_name         text CHECK (length(signed_name) <= 120),
            created_by          uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            CHECK ((content IS NULL) <> (storage_key IS NULL)),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX client_documents_client ON app.client_documents (tenant_id, client_id)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.client_documents TO app_api")
    _tenant_policy("client_documents")
    # A client sees what was shared with them and what they uploaded; uploads are theirs.
    op.execute("""
        CREATE POLICY client_documents_client_read ON app.client_documents FOR SELECT
        TO app_api
        USING (client_id = app.current_client_id() AND (shared OR uploaded_by_client))
    """)
    op.execute("""
        CREATE POLICY client_documents_client_upload ON app.client_documents FOR INSERT
        TO app_api
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id()
                    AND uploaded_by_client AND NOT shared AND NOT sign_requested)
    """)
    op.execute("""
        CREATE FUNCTION app.sign_document(p_document uuid, p_name text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF length(trim(coalesce(p_name, ''))) = 0 THEN
                RAISE EXCEPTION 'a name is needed' USING ERRCODE = '22004';
            END IF;
            UPDATE app.client_documents
            SET signed_at = now(), signed_name = left(trim(p_name), 120)
            WHERE id = p_document AND client_id = app.current_client_id()
              AND shared AND sign_requested AND signed_at IS NULL;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'nothing to sign' USING ERRCODE = 'P0002';
            END IF;
        END
        $$
    """)
    # A signed link (checked by the API) opens one file without a signed-in user.
    op.execute("""
        CREATE FUNCTION app.document_file(p_document uuid, p_tenant uuid)
        RETURNS TABLE (name text, content_type text, content bytea, storage_key text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT d.name, d.content_type, d.content, d.storage_key FROM app.client_documents d
            WHERE d.id = p_document AND d.tenant_id = p_tenant
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.document_file(uuid, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.document_file(uuid, uuid) TO app_api")
    op.execute("REVOKE ALL ON FUNCTION app.sign_document(uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.sign_document(uuid, text) TO app_api")

    op.execute("""
        ALTER TABLE app.quotes
            ADD COLUMN kind text NOT NULL DEFAULT 'quote' CHECK (kind IN ('quote', 'bill')),
            ADD COLUMN period_start date,
            ADD COLUMN period_end date
    """)
    op.execute(QUOTE_BY_TOKEN)

    op.execute("""
        CREATE TABLE app.time_entries (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id    uuid NOT NULL,
            user_id      uuid NOT NULL REFERENCES app.users (id),
            day          date NOT NULL,
            minutes      integer NOT NULL CHECK (minutes BETWEEN 1 AND 1440),
            description  text NOT NULL CHECK (length(trim(description)) BETWEEN 1 AND 500),
            billable     boolean NOT NULL DEFAULT true,
            bill_id      uuid REFERENCES app.quotes (id) ON DELETE SET NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX time_entries_client ON app.time_entries (tenant_id, client_id, day)")
    op.execute("CREATE INDEX time_entries_user ON app.time_entries (tenant_id, user_id, day)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.time_entries TO app_api")
    _tenant_policy("time_entries")

    op.execute("""
        CREATE TABLE app.retainers (
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id         uuid NOT NULL,
            monthly_amount    integer NOT NULL DEFAULT 0 CHECK (monthly_amount >= 0),
            included_minutes  integer NOT NULL DEFAULT 0 CHECK (included_minutes >= 0),
            hourly_rate       integer NOT NULL DEFAULT 0 CHECK (hourly_rate >= 0),
            currency          char(3) NOT NULL,
            active            boolean NOT NULL DEFAULT true,
            updated_at        timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, client_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.retainers TO app_api")
    _tenant_policy("retainers")


def downgrade() -> None:
    op.execute("DROP TABLE app.retainers")
    op.execute("DROP TABLE app.time_entries")
    op.execute(OLD_QUOTE_BY_TOKEN)
    op.execute("DELETE FROM app.quotes WHERE kind = 'bill'")
    op.execute("""
        ALTER TABLE app.quotes DROP COLUMN period_end, DROP COLUMN period_start,
            DROP COLUMN kind
    """)
    op.execute("DROP FUNCTION app.document_file(uuid, uuid)")
    op.execute("DROP FUNCTION app.sign_document(uuid, text)")
    op.execute("DROP TABLE app.client_documents")
