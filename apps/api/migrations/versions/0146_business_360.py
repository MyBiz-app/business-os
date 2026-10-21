"""The business 360 card in the console (slice K2): notes, tags, an account owner, a timeline.

Two tables of MyBiz's own, like the other console tables not reachable from the API role: only
SECURITY DEFINER functions touch them, and they check the console permission.

- `platform_business_notes`: internal notes the team writes about a business ("I spoke to them,
  they want X"). Never shown to the business.
- `platform_business_cards`: tags and the account owner (the MyBiz team member who looks after
  the business).

`platform_business_timeline` joins what the console already knows about one business (sign-up,
trial end, invoices, requests, changes the team made, notes) into one list, newest first.
`platform_trials_ending` lists the businesses whose free trial ends soon, for quick actions.

Revision ID: 0146
Revises: 0145
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0146"
down_revision: str | None = "0145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "platform_business_card(uuid)",
    "platform_business_card_set(uuid, text[], text)",
    "platform_business_notes(uuid)",
    "platform_business_note_add(uuid, text)",
    "platform_business_timeline(uuid)",
    "platform_trials_ending(integer)",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.platform_business_notes (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            author_email  text NOT NULL,
            body          text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 2000),
            created_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX platform_business_notes_tenant "
        "ON app.platform_business_notes (tenant_id, created_at DESC)"
    )
    op.execute("""
        CREATE TABLE app.platform_business_cards (
            tenant_id      uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            tags           text[] NOT NULL DEFAULT '{}' CHECK (cardinality(tags) <= 12),
            account_owner  text,
            updated_by     text NOT NULL,
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
    """)
    for table in ("platform_business_notes", "platform_business_cards"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")  # no API access
        op.execute(f"REVOKE ALL ON app.{table} FROM app_api")

    op.execute("""
        CREATE FUNCTION app.platform_business_card(p_tenant uuid)
        RETURNS TABLE (tags text[], account_owner text, updated_by text, updated_at timestamptz,
                       trial_ends_at timestamptz, closed_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('businesses.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            RETURN QUERY
            SELECT coalesce(c.tags, '{}'::text[]), c.account_owner, c.updated_by, c.updated_at,
                   t.trial_ends_at, t.closed_at
            FROM app.tenants t
            LEFT JOIN app.platform_business_cards c ON c.tenant_id = t.id
            WHERE t.id = p_tenant;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_business_card_set(
            p_tenant uuid, p_tags text[], p_account_owner text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_email text := (SELECT m.email FROM app.platform_me() m);
            v_tags text[];
            v_owner text := nullif(lower(trim(coalesce(p_account_owner, ''))), '');
        BEGIN
            IF NOT app.platform_can('businesses.act') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            -- Tags: trimmed, lower case, no empty ones, no repeats.
            SELECT coalesce(array_agg(DISTINCT x ORDER BY x), '{}')
            INTO v_tags
            FROM (SELECT lower(trim(tag)) AS x FROM unnest(coalesce(p_tags, '{}')) AS tag) s
            WHERE x <> '';
            IF cardinality(v_tags) > 12 OR EXISTS (
                SELECT 1 FROM unnest(v_tags) AS x WHERE length(x) > 30
            ) THEN
                RAISE EXCEPTION 'invalid_tags' USING ERRCODE = 'P0001';
            END IF;
            IF v_owner IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM app.platform_staff s WHERE s.email = v_owner AND NOT s.disabled
            ) THEN
                RAISE EXCEPTION 'unknown_account_owner' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.platform_business_cards
                (tenant_id, tags, account_owner, updated_by)
            VALUES (p_tenant, v_tags, v_owner, v_email)
            ON CONFLICT (tenant_id) DO UPDATE
            SET tags = excluded.tags, account_owner = excluded.account_owner,
                updated_by = excluded.updated_by, updated_at = now();
            PERFORM app.platform_audit_add(
                'business.card_updated', p_tenant,
                jsonb_build_object('tags', v_tags, 'account_owner', v_owner));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_business_notes(p_tenant uuid)
        RETURNS TABLE (id uuid, author_email text, body text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('businesses.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT n.id, n.author_email, n.body, n.created_at
            FROM app.platform_business_notes n WHERE n.tenant_id = p_tenant
            ORDER BY n.created_at DESC LIMIT 200;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_business_note_add(p_tenant uuid, p_body text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_email text := (SELECT m.email FROM app.platform_me() m);
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('businesses.act') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            IF length(trim(coalesce(p_body, ''))) NOT BETWEEN 1 AND 2000 THEN
                RAISE EXCEPTION 'invalid_note' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.platform_business_notes (tenant_id, author_email, body)
            VALUES (p_tenant, v_email, trim(p_body))
            RETURNING platform_business_notes.id INTO v_id;
            PERFORM app.platform_audit_add(
                'business.note_added', p_tenant, jsonb_build_object('note', v_id));
            RETURN v_id;
        END
        $$
    """)
    # One list of everything the console knows about a business. Parts the caller may not read
    # (invoices need billing.manage, requests need inbox.manage) are left out.
    op.execute("""
        CREATE FUNCTION app.platform_business_timeline(p_tenant uuid)
        RETURNS TABLE (at timestamptz, kind text, actor text, details jsonb)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('businesses.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app.tenants WHERE id = p_tenant) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            RETURN QUERY
            SELECT e.at, e.kind, e.actor, e.details FROM (
                SELECT t.created_at AS at, 'signup'::text AS kind, NULL::text AS actor,
                       '{}'::jsonb AS details
                FROM app.tenants t WHERE t.id = p_tenant
                UNION ALL
                SELECT t.trial_ends_at, 'trial_ends', NULL, '{}'::jsonb
                FROM app.tenants t WHERE t.id = p_tenant
                UNION ALL
                SELECT t.closed_at, 'closed', NULL, '{}'::jsonb
                FROM app.tenants t WHERE t.id = p_tenant AND t.closed_at IS NOT NULL
                UNION ALL
                SELECT i.issued_at, 'invoice', NULL,
                       jsonb_build_object('number', i.number, 'total', i.total,
                                          'currency', i.currency, 'status', i.status)
                FROM app.platform_invoices i
                WHERE i.tenant_id = p_tenant AND app.platform_can('billing.manage')
                UNION ALL
                SELECT r.created_at, 'request', NULL,
                       jsonb_build_object('status', r.status,
                                          'from_business', r.tenant_id IS NOT NULL)
                FROM app.contact_requests r
                WHERE r.tenant_id = p_tenant AND app.platform_can('inbox.manage')
                UNION ALL
                SELECT a.occurred_at, 'change', a.actor_email,
                       jsonb_build_object('action', a.action)
                       || CASE WHEN a.action IN ('business.trial_extended',
                                                 'business.modules_changed')
                               THEN a.details ELSE '{}'::jsonb END
                FROM app.platform_audit a
                WHERE a.business_id = p_tenant
                  AND a.action IN ('business.trial_extended', 'business.modules_changed',
                                   'business.invoice_voided', 'business.card_updated')
                UNION ALL
                SELECT n.created_at, 'note', n.author_email,
                       jsonb_build_object('id', n.id, 'body', n.body)
                FROM app.platform_business_notes n WHERE n.tenant_id = p_tenant
            ) e
            ORDER BY e.at DESC LIMIT 150;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_trials_ending(p_days integer)
        RETURNS TABLE (tenant_id uuid, name text, owner_email text, trial_ends_at timestamptz,
                       active_clients integer, has_card boolean, account_owner text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('businesses.read') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            -- Trials that end within p_days, and the ones that ended in the last three days.
            RETURN QUERY
            SELECT t.id, t.name,
                   (SELECT u.email FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = t.id AND m.role = 'owner'
                    ORDER BY m.created_at LIMIT 1),
                   t.trial_ends_at,
                   (SELECT count(DISTINCT e.client_id)::int FROM app.entitlements e
                    WHERE e.tenant_id = t.id AND e.status = 'active'
                      AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on),
                   coalesce((SELECT b.card_last4 IS NOT NULL FROM app.billing_accounts b
                             WHERE b.tenant_id = t.id), false),
                   c.account_owner
            FROM app.tenants t
            LEFT JOIN app.platform_business_cards c ON c.tenant_id = t.id
            WHERE t.closed_at IS NULL
              AND t.trial_ends_at BETWEEN now() - interval '3 days'
                                      AND now() + make_interval(
                                          days => least(greatest(p_days, 1), 30))
            ORDER BY t.trial_ends_at LIMIT 200;
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    # contract: only the downgrade drops anything; the two tables and six functions are new in this
    # migration, so the previous release never reads them
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.platform_business_cards")
    op.execute("DROP TABLE app.platform_business_notes")
