"""Branch-targeted messages (round 5, F4).

A business's message can now go to some of its branches (or a branch group), over more channels,
and to its staff:
- `campaigns` remembers the branches (`location_ids`, null = the whole network), the channels and
  who it went to (`audience` 'staff' = the business's staff).
- Email, push and pop-up go through the broadcast engine (M1): the business issues an
  `announcements` row (issuer 'tenant'); WhatsApp and SMS keep using the business's outbox.
- The sender needs a first name per delivery (`announcement_deliveries.first_name`) so the text
  can still say "Hi {first_name}".
- The recipients of a business announcement are resolved by a SECURITY DEFINER function that only
  the sender job can call; the business creates its announcement through
  `app.tenant_announcement_create`, which is always filed under the caller's own business.
- The console's list shows MyBiz's own broadcasts only.

Revision ID: 0101
Revises: 0100
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0101"
down_revision: str | None = "0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAMPAIGN_CHANNELS = ("whatsapp", "sms", "email", "push", "popup")


def upgrade() -> None:
    op.execute("ALTER TABLE app.campaigns DROP CONSTRAINT campaigns_channel_check")
    op.execute(f"""
        ALTER TABLE app.campaigns ADD CONSTRAINT campaigns_channel_check
        CHECK (channel IN {CAMPAIGN_CHANNELS!r})
    """)
    op.execute("ALTER TABLE app.campaigns ADD COLUMN channels text[]")
    op.execute("ALTER TABLE app.campaigns ADD COLUMN location_ids uuid[]")
    op.execute("ALTER TABLE app.announcement_deliveries ADD COLUMN first_name text")

    # Who gets a business announcement: explicit client and member ids chosen by the API when
    # the message was sent (branch and segment rules already applied there). Not callable by
    # the API.
    op.execute("""
        CREATE FUNCTION app.tenant_announcement_recipients(
            p_tenant uuid, p_audience jsonb, p_kind text
        ) RETURNS TABLE (person_key text, email text, phone text, user_id uuid, client_id uuid,
                         tenant_id uuid, locale text, groups text[], has_push boolean,
                         first_name text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            WITH people AS (
                SELECT 'clients'::text AS grp, lower(c.email) AS email, c.phone,
                       c.user_id, c.id AS client_id, c.tenant_id,
                       coalesce(u.locale, t.locale) AS locale, c.first_name
                FROM app.clients c
                JOIN app.tenants t ON t.id = c.tenant_id
                LEFT JOIN app.users u ON u.id = c.user_id
                WHERE c.tenant_id = p_tenant AND c.erased_at IS NULL
                  AND c.id IN (SELECT jsonb_array_elements_text(
                                   coalesce(p_audience -> 'client_ids', '[]'))::uuid)
                  AND (p_kind <> 'marketing'
                       OR c.marketing_consent_at IS NOT NULL
                       OR u.marketing_consent_at IS NOT NULL)
              UNION ALL
                SELECT 'staff', lower(u.email), NULL, u.id, NULL, m.tenant_id,
                       coalesce(u.locale, t.locale),
                       coalesce(nullif(split_part(trim(u.full_name), ' ', 1), ''),
                                split_part(u.email, '@', 1))
                FROM app.tenant_members m
                JOIN app.tenants t ON t.id = m.tenant_id
                JOIN app.users u ON u.id = m.user_id
                WHERE m.tenant_id = p_tenant
                  AND m.user_id IN (SELECT jsonb_array_elements_text(
                                        coalesce(p_audience -> 'user_ids', '[]'))::uuid)
                  AND (p_kind <> 'marketing' OR u.marketing_consent_at IS NOT NULL)
            ),
            keyed AS (
                SELECT p.*, coalesce(p.email, 'u:' || p.user_id::text, 'c:' || p.client_id::text)
                       AS pkey
                FROM people p
                WHERE p.email IS NOT NULL OR p.user_id IS NOT NULL OR p.client_id IS NOT NULL
            )
            SELECT k.pkey,
                   (array_agg(k.email) FILTER (WHERE k.email IS NOT NULL))[1],
                   (array_agg(k.phone) FILTER (WHERE k.phone IS NOT NULL))[1],
                   (array_agg(k.user_id) FILTER (WHERE k.user_id IS NOT NULL))[1],
                   (array_agg(k.client_id) FILTER (WHERE k.client_id IS NOT NULL))[1],
                   (array_agg(k.tenant_id) FILTER (WHERE k.tenant_id IS NOT NULL))[1],
                   min(k.locale),
                   array_agg(DISTINCT k.grp ORDER BY k.grp),
                   bool_or(EXISTS (SELECT 1 FROM app.push_tokens pt WHERE pt.user_id = k.user_id)),
                   min(k.first_name)
            FROM keyed k
            GROUP BY k.pkey
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app.tenant_announcement_recipients(uuid, jsonb, text) FROM PUBLIC"
    )

    # A business sends an email / push / pop-up message: always filed under its own business.
    op.execute("""
        CREATE FUNCTION app.tenant_announcement_create(
            p_kind text, p_channels text[], p_audience jsonb, p_content jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_tenant uuid := app.current_tenant_id();
            v_id uuid;
        BEGIN
            IF v_tenant IS NULL OR app.current_user_id() IS NULL THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF p_kind NOT IN ('marketing', 'service')
               OR cardinality(p_channels) = 0
               OR NOT p_channels <@ ARRAY['email', 'push', 'popup']::text[] THEN
                RAISE EXCEPTION 'bad_request' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.announcements
                (issuer, tenant_id, kind, channels, audience, content, status, scheduled_at,
                 created_by)
            VALUES ('tenant', v_tenant, p_kind, p_channels, p_audience, p_content,
                    'scheduled', now(),
                    (SELECT u.email FROM app.users u WHERE u.id = app.current_user_id()))
            RETURNING announcements.id INTO v_id;
            RETURN v_id;
        END
        $$
    """)

    # Which of these people (members of the caller's business, or its clients) have a phone to
    # push to: the push tokens themselves are private to their owner.
    op.execute("""
        CREATE FUNCTION app.users_with_push(p_user_ids uuid[]) RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT DISTINCT pt.user_id FROM app.push_tokens pt
            WHERE pt.user_id = ANY (p_user_ids)
              AND app.current_tenant_id() IS NOT NULL
              AND (EXISTS (SELECT 1 FROM app.tenant_members m
                           WHERE m.user_id = pt.user_id AND m.tenant_id = app.current_tenant_id())
                   OR EXISTS (SELECT 1 FROM app.clients c
                              WHERE c.user_id = pt.user_id
                                AND c.tenant_id = app.current_tenant_id()))
        $$
    """)
    for function in (
        "tenant_announcement_create(text, text[], jsonb, jsonb)",
        "users_with_push(uuid[])",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")

    # The console lists MyBiz's own broadcasts only.
    op.execute("""CREATE OR REPLACE FUNCTION app.announcement_rows(p_id uuid)
        RETURNS TABLE (id uuid, kind text, channels text[], audience jsonb, content jsonb,
                       scheduled_at timestamptz, status text, recipient_count integer,
                       created_by text, created_at timestamptz, sent_at timestamptz, stats jsonb)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT a.id, a.kind, a.channels, a.audience, a.content, a.scheduled_at, a.status,
                   a.recipient_count, a.created_by, a.created_at, a.sent_at,
                   (SELECT jsonb_build_object(
                        'queued', count(*) FILTER (WHERE d.status = 'queued'),
                        'sent', count(*) FILTER (WHERE d.status = 'sent'),
                        'failed', count(*) FILTER (WHERE d.status = 'failed'),
                        'skipped', count(*) FILTER (WHERE d.status = 'skipped'),
                        'unsubscribed', count(*) FILTER (WHERE d.unsubscribed_at IS NOT NULL),
                        'sent_by_channel', coalesce((
                            SELECT jsonb_object_agg(x.channel, x.n) FROM (
                                SELECT d2.channel, count(*) AS n
                                FROM app.announcement_deliveries d2
                                WHERE d2.announcement_id = a.id AND d2.status = 'sent'
                                GROUP BY d2.channel) x), '{}'))
                    FROM app.announcement_deliveries d WHERE d.announcement_id = a.id)
                   || (SELECT jsonb_build_object('viewed', count(v.first_viewed_at),
                                                 'clicked', count(v.clicked_at))
                       FROM app.announcement_views v WHERE v.announcement_id = a.id)
            FROM app.announcements a
            WHERE a.issuer = 'platform' AND (p_id IS NULL OR a.id = p_id)
            ORDER BY a.created_at DESC LIMIT 200;
        END
        $$""")


def downgrade() -> None:
    op.execute("""CREATE OR REPLACE FUNCTION app.announcement_rows(p_id uuid)
        RETURNS TABLE (id uuid, kind text, channels text[], audience jsonb, content jsonb,
                       scheduled_at timestamptz, status text, recipient_count integer,
                       created_by text, created_at timestamptz, sent_at timestamptz, stats jsonb)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT a.id, a.kind, a.channels, a.audience, a.content, a.scheduled_at, a.status,
                   a.recipient_count, a.created_by, a.created_at, a.sent_at,
                   (SELECT jsonb_build_object(
                        'queued', count(*) FILTER (WHERE d.status = 'queued'),
                        'sent', count(*) FILTER (WHERE d.status = 'sent'),
                        'failed', count(*) FILTER (WHERE d.status = 'failed'),
                        'skipped', count(*) FILTER (WHERE d.status = 'skipped'),
                        'unsubscribed', count(*) FILTER (WHERE d.unsubscribed_at IS NOT NULL),
                        'sent_by_channel', coalesce((
                            SELECT jsonb_object_agg(x.channel, x.n) FROM (
                                SELECT d2.channel, count(*) AS n
                                FROM app.announcement_deliveries d2
                                WHERE d2.announcement_id = a.id AND d2.status = 'sent'
                                GROUP BY d2.channel) x), '{}'))
                    FROM app.announcement_deliveries d WHERE d.announcement_id = a.id)
                   || (SELECT jsonb_build_object('viewed', count(v.first_viewed_at),
                                                 'clicked', count(v.clicked_at))
                       FROM app.announcement_views v WHERE v.announcement_id = a.id)
            FROM app.announcements a
            WHERE p_id IS NULL OR a.id = p_id
            ORDER BY a.created_at DESC LIMIT 200;
        END
        $$""")
    op.execute("DROP FUNCTION app.users_with_push(uuid[])")
    op.execute("DROP FUNCTION app.tenant_announcement_create(text, text[], jsonb, jsonb)")
    op.execute("DROP FUNCTION app.tenant_announcement_recipients(uuid, jsonb, text)")
    op.execute("DELETE FROM app.announcements WHERE issuer = 'tenant'")
    op.execute("ALTER TABLE app.announcement_deliveries DROP COLUMN first_name")
    op.execute("ALTER TABLE app.campaigns DROP COLUMN location_ids")
    op.execute("ALTER TABLE app.campaigns DROP COLUMN channels")
    op.execute("DELETE FROM app.campaigns WHERE channel NOT IN ('whatsapp', 'sms')")
    op.execute("ALTER TABLE app.campaigns DROP CONSTRAINT campaigns_channel_check")
    op.execute("""
        ALTER TABLE app.campaigns ADD CONSTRAINT campaigns_channel_check
        CHECK (channel IN ('whatsapp', 'sms'))
    """)
