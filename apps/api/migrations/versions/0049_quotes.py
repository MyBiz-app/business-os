"""Quotes, deposits and event projects (#44, decision X12).

- A quote (`app.quotes`) is for a client: a number per business (1001, 1002…), a title, lines
  (`app.quote_lines`: description, quantity, unit price), its total, a deposit percentage, an
  optional event (date and time, place), valid until a date, and notes / terms.
- Statuses: draft → sent → accepted or declined. Only a draft is edited. A sent quote past its
  date reads as expired (computed, not stored).
- The client sees it by a private link (`token`, no sign-in) or in the client app, and accepts
  it with their name. SECURITY DEFINER functions serve the link: app.quote_by_token,
  app.accept_quote and app.pay_quote_deposit (simulated until a payment provider is chosen).
- Payments can be for a quote (`payments.quote_id`); its receipt says what was paid.
- A checkout can be for a quote's deposit (`checkouts.quote_id`, no plan): with a real payments
  provider (X13) the client pays it on the provider's page and its webhook completes it;
  app.finish_checkout records the payment against the quote.

Revision ID: 0049
Revises: 0048
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FINISH_WITH_QUOTES = """
    CREATE OR REPLACE FUNCTION app.finish_checkout(p_checkout_id uuid, p_ref text) RETURNS uuid
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
        IF v.quote_id IS NOT NULL THEN
            -- A quote's deposit: the payment is the quote's; no plan is created.
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, provider_ref,
                 idempotency_key, quote_id, description)
            SELECT v.tenant_id, v.client_id, v.amount, v.currency, 'succeeded', v.provider,
                   coalesce(p_ref, v.provider_ref), 'checkout:' || v.id, q.id,
                   left(q.title, 180) || ' · ' || q.number
            FROM app.quotes q WHERE q.id = v.quote_id;
            UPDATE app.checkouts
            SET status = 'paid', completed_at = now(), provider_ref = coalesce(p_ref, provider_ref)
            WHERE id = v.id;
            RETURN NULL;
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
FINISH_PLANS_ONLY = """
    CREATE OR REPLACE FUNCTION app.finish_checkout(p_checkout_id uuid, p_ref text) RETURNS uuid
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


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.quote_counters (
            tenant_id  uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            last       integer NOT NULL
        )
    """)
    op.execute("ALTER TABLE app.quote_counters ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT ON app.quote_counters TO app_api")
    op.execute("""
        CREATE POLICY quote_counters_tenant ON app.quote_counters FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.quotes (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id        uuid NOT NULL,
            number           integer NOT NULL,
            title            text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 120),
            status           text NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft', 'sent', 'accepted', 'declined')),
            currency         char(3) NOT NULL,
            deposit_percent  integer NOT NULL DEFAULT 0 CHECK (deposit_percent BETWEEN 0 AND 100),
            valid_until      date,
            event_starts_at  timestamptz,
            event_place      text CHECK (length(event_place) <= 200),
            notes            text CHECK (length(notes) <= 4000),
            -- The private link: two random UUIDs (about 244 random bits).
            token            text NOT NULL UNIQUE DEFAULT
                             replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''),
            sent_at          timestamptz,
            accepted_at      timestamptz,
            accepted_name    text CHECK (length(accepted_name) <= 120),
            declined_at      timestamptz,
            created_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, number),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX quotes_client ON app.quotes (tenant_id, client_id)")
    op.execute("CREATE INDEX quotes_event ON app.quotes (tenant_id, event_starts_at)")
    op.execute("""
        CREATE TABLE app.quote_lines (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL,
            quote_id     uuid NOT NULL,
            position     integer NOT NULL,
            description  text NOT NULL CHECK (length(trim(description)) BETWEEN 1 AND 300),
            quantity     numeric(10, 2) NOT NULL CHECK (quantity > 0 AND quantity <= 100000),
            unit_price   integer NOT NULL CHECK (unit_price >= 0),
            FOREIGN KEY (tenant_id, quote_id) REFERENCES app.quotes (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX quote_lines_quote ON app.quote_lines (quote_id, position)")
    for table in ("quotes", "quote_lines"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)
    # Clients read their own sent quotes in the app (never drafts).
    op.execute("""
        CREATE POLICY quotes_client ON app.quotes FOR SELECT TO app_api
        USING (client_id = app.current_client_id() AND status <> 'draft')
    """)
    op.execute("""
        CREATE POLICY quote_lines_client ON app.quote_lines FOR SELECT TO app_api
        USING (EXISTS (
            SELECT 1 FROM app.quotes q WHERE q.id = quote_id
              AND q.client_id = app.current_client_id() AND q.status <> 'draft'
        ))
    """)

    op.execute("""
        ALTER TABLE app.payments ADD COLUMN quote_id uuid
            REFERENCES app.quotes (id) ON DELETE SET NULL
    """)
    op.execute("CREATE INDEX payments_quote ON app.payments (quote_id) WHERE quote_id IS NOT NULL")

    # The next quote number of the current business (1001, 1002…); the row lock orders them.
    op.execute("""
        CREATE FUNCTION app.next_quote_number() RETURNS integer
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = '' AS $$
            INSERT INTO app.quote_counters AS c (tenant_id, last)
            VALUES (app.current_tenant_id(), 1001)
            ON CONFLICT (tenant_id) DO UPDATE SET last = c.last + 1
            RETURNING last
        $$
    """)

    # A quote's total in minor units: the sum of its lines (quantity times unit price, rounded).
    op.execute("""
        CREATE FUNCTION app.quote_total(p_quote uuid) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT coalesce(round(sum(l.quantity * l.unit_price))::integer, 0)
            FROM app.quote_lines l WHERE l.quote_id = p_quote
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.quote_paid(p_quote uuid) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT coalesce(sum(p.amount), 0)::integer FROM app.payments p
            WHERE p.quote_id = p_quote AND p.status = 'succeeded'
        $$
    """)

    # The private link: what the client sees, without signing in.
    op.execute("""
        CREATE FUNCTION app.quote_by_token(p_token text) RETURNS jsonb
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
    """)
    op.execute("""
        CREATE FUNCTION app.answer_quote(p_token text, p_accept boolean, p_name text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_quote record;
        BEGIN
            SELECT q.id, q.status, q.valid_until, t.time_zone INTO v_quote
            FROM app.quotes q JOIN app.tenants t ON t.id = q.tenant_id
            WHERE q.token = p_token FOR UPDATE OF q;
            IF v_quote.id IS NULL OR v_quote.status = 'draft' THEN
                RAISE EXCEPTION 'no such quote' USING ERRCODE = 'P0002';
            END IF;
            IF v_quote.status <> 'sent' THEN
                RAISE EXCEPTION 'already answered' USING ERRCODE = '55000';
            END IF;
            IF v_quote.valid_until < (now() AT TIME ZONE v_quote.time_zone)::date THEN
                RAISE EXCEPTION 'expired' USING ERRCODE = '22008';
            END IF;
            IF p_accept AND length(trim(coalesce(p_name, ''))) = 0 THEN
                RAISE EXCEPTION 'a name is needed' USING ERRCODE = '22004';
            END IF;
            UPDATE app.quotes SET
                status = CASE WHEN p_accept THEN 'accepted' ELSE 'declined' END,
                accepted_at = CASE WHEN p_accept THEN now() END,
                accepted_name = CASE WHEN p_accept THEN left(trim(p_name), 120) END,
                declined_at = CASE WHEN p_accept THEN NULL ELSE now() END,
                updated_at = now()
            WHERE id = v_quote.id;
        END
        $$
    """)
    # The deposit of an accepted quote, paid from its link (simulated until a provider is set).
    op.execute("""
        CREATE FUNCTION app.pay_quote_deposit(p_token text, p_key text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_quote record;
            v_due integer;
            v_id uuid;
        BEGIN
            SELECT q.id, q.tenant_id, q.client_id, q.currency, q.number, q.title,
                   q.deposit_percent, q.status
            INTO v_quote FROM app.quotes q WHERE q.token = p_token FOR UPDATE;
            IF v_quote.id IS NULL OR v_quote.status <> 'accepted' THEN
                RAISE EXCEPTION 'no accepted quote' USING ERRCODE = 'P0002';
            END IF;
            SELECT id INTO v_id FROM app.payments
            WHERE tenant_id = v_quote.tenant_id AND idempotency_key = p_key;
            IF v_id IS NOT NULL THEN
                RETURN v_id;  -- the same payment again
            END IF;
            v_due := round(app.quote_total(v_quote.id) * v_quote.deposit_percent / 100.0)::integer
                     - app.quote_paid(v_quote.id);
            IF v_due <= 0 THEN
                RAISE EXCEPTION 'nothing due' USING ERRCODE = '55000';
            END IF;
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, method,
                 idempotency_key, quote_id, description)
            VALUES (v_quote.tenant_id, v_quote.client_id, v_due, v_quote.currency, 'succeeded',
                    'simulated', 'card', p_key, v_quote.id,
                    left(v_quote.title, 180) || ' · ' || v_quote.number)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    # A deposit through a payments provider: a checkout for the quote.
    op.execute("ALTER TABLE app.checkouts ALTER COLUMN plan_id DROP NOT NULL")
    op.execute("""
        ALTER TABLE app.checkouts ADD COLUMN quote_id uuid
            REFERENCES app.quotes (id) ON DELETE CASCADE,
            ADD CONSTRAINT checkouts_plan_or_quote CHECK ((plan_id IS NULL) <> (quote_id IS NULL))
    """)
    op.execute(FINISH_WITH_QUOTES)
    op.execute("""
        CREATE FUNCTION app.start_quote_checkout(p_token text, p_provider text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_quote record;
            v_due integer;
            v_id uuid;
        BEGIN
            SELECT q.id, q.tenant_id, q.client_id, q.currency, q.deposit_percent, q.status
            INTO v_quote FROM app.quotes q WHERE q.token = p_token FOR UPDATE;
            IF v_quote.id IS NULL OR v_quote.status <> 'accepted' THEN
                RAISE EXCEPTION 'no accepted quote' USING ERRCODE = 'P0002';
            END IF;
            v_due := round(app.quote_total(v_quote.id) * v_quote.deposit_percent / 100.0)::integer
                     - app.quote_paid(v_quote.id);
            IF v_due <= 0 THEN
                RAISE EXCEPTION 'nothing due' USING ERRCODE = '55000';
            END IF;
            INSERT INTO app.checkouts
                (tenant_id, client_id, quote_id, amount, list_amount, currency, provider)
            VALUES (v_quote.tenant_id, v_quote.client_id, v_quote.id, v_due, v_due,
                    v_quote.currency, p_provider)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.set_checkout_page(p_checkout uuid, p_url text, p_ref text)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = '' AS $$
            UPDATE app.checkouts SET pay_url = p_url, provider_ref = p_ref
            WHERE id = p_checkout AND status = 'pending' AND quote_id IS NOT NULL
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.quote_tenant(p_token text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT tenant_id FROM app.quotes WHERE token = p_token AND status <> 'draft'
        $$
    """)
    for signature in (
        "app.start_quote_checkout(text, text)",
        "app.set_checkout_page(uuid, text, text)",
        "app.quote_tenant(text)",
        "app.next_quote_number()",
        "app.quote_total(uuid)",
        "app.quote_paid(uuid)",
        "app.quote_by_token(text)",
        "app.answer_quote(text, boolean, text)",
        "app.pay_quote_deposit(text, text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.quote_tenant(text)")
    op.execute("DROP FUNCTION app.set_checkout_page(uuid, text, text)")
    op.execute("DROP FUNCTION app.start_quote_checkout(text, text)")
    op.execute(FINISH_PLANS_ONLY)
    op.execute("DELETE FROM app.checkouts WHERE quote_id IS NOT NULL")
    op.execute("""
        ALTER TABLE app.checkouts DROP CONSTRAINT checkouts_plan_or_quote,
            DROP COLUMN quote_id
    """)
    op.execute("ALTER TABLE app.checkouts ALTER COLUMN plan_id SET NOT NULL")
    for signature in (
        "app.pay_quote_deposit(text, text)",
        "app.answer_quote(text, boolean, text)",
        "app.quote_by_token(text)",
        "app.quote_paid(uuid)",
        "app.quote_total(uuid)",
        "app.next_quote_number()",
    ):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP INDEX app.payments_quote")
    op.execute("ALTER TABLE app.payments DROP COLUMN quote_id")
    op.execute("DROP TABLE app.quote_lines")
    op.execute("DROP TABLE app.quotes")
    op.execute("DROP TABLE app.quote_counters")
