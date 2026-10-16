"""Broadcast center (round 5, M1): announcements, their deliveries and who has seen them.

One engine sends a message to a mix of audiences (MyBiz team, business owners, business staff,
the businesses' clients) over several channels (email, push, pop-up, WhatsApp, SMS). A person who
falls in several audiences gets it once. A marketing message goes only to people who agreed to
receive it (Communications Law, section 30A) and every one carries a way to opt out; a service
message (maintenance, a new version) goes to everyone.

The audience is resolved by SECURITY DEFINER functions, because the console reads across
businesses. The raw resolver is not callable by the API; every console function checks the
caller, and the tables themselves have no API access. A new console permission, `broadcasts.manage`,
guards the whole feature.

Revision ID: 0088
Revises: 0082
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0088"
down_revision: str | None = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PERMISSIONS = (
    "businesses.read",
    "businesses.act",
    "billing.manage",
    "inbox.manage",
    "usage.read",
    "staff.manage",
)
PERMISSIONS = (*OLD_PERMISSIONS, "broadcasts.manage")

CHANNELS = ("email", "push", "popup", "whatsapp", "sms")


def _me(permissions: tuple[str, ...]) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION app.platform_me()
        RETURNS TABLE (email text, level text, permissions text[])
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT s.email, s.level,
                   CASE WHEN s.level IN ('primary_owner', 'owner')
                        THEN ARRAY{list(permissions)}::text[] ELSE s.permissions END
            FROM app.platform_staff s
            JOIN app.users u ON lower(u.email) = s.email
            WHERE u.id = app.current_user_id() AND NOT s.disabled
        $$
    """


def upgrade() -> None:
    # The new console permission.
    op.execute("ALTER TABLE app.platform_staff DROP CONSTRAINT platform_staff_permissions_check")
    op.execute(f"""
        ALTER TABLE app.platform_staff ADD CONSTRAINT platform_staff_permissions_check
        CHECK (permissions <@ ARRAY{list(PERMISSIONS)}::text[])
    """)
    op.execute(_me(PERMISSIONS))

    # Consent to marketing messages; a service message needs none.
    op.execute("ALTER TABLE app.users ADD COLUMN marketing_consent_at timestamptz")
    op.execute("ALTER TABLE app.clients ADD COLUMN marketing_consent_at timestamptz")

    op.execute(f"""
        CREATE TABLE app.announcements (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            issuer           text NOT NULL DEFAULT 'platform'
                             CHECK (issuer IN ('platform', 'tenant')),
            tenant_id        uuid REFERENCES app.tenants (id) ON DELETE CASCADE,
            kind             text NOT NULL CHECK (kind IN ('marketing', 'service')),
            channels         text[] NOT NULL
                             CHECK (cardinality(channels) > 0
                                    AND channels <@ ARRAY{list(CHANNELS)}::text[]),
            audience         jsonb NOT NULL DEFAULT '{{}}',
            content          jsonb NOT NULL DEFAULT '{{}}',
            scheduled_at     timestamptz,
            status           text NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft', 'scheduled', 'sending', 'sent',
                                               'cancelled')),
            recipient_count  integer,
            created_by       text NOT NULL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            sent_at          timestamptz,
            CHECK ((issuer = 'platform') = (tenant_id IS NULL))
        )
    """)
    op.execute("CREATE INDEX announcements_due ON app.announcements (status, scheduled_at)")
    op.execute("""
        CREATE TABLE app.announcement_deliveries (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            announcement_id  uuid NOT NULL REFERENCES app.announcements (id) ON DELETE CASCADE,
            channel          text NOT NULL,
            person_key       text NOT NULL,
            user_id          uuid REFERENCES app.users (id) ON DELETE CASCADE,
            client_id        uuid REFERENCES app.clients (id) ON DELETE SET NULL,
            tenant_id        uuid REFERENCES app.tenants (id) ON DELETE SET NULL,
            email            text,
            phone            text,
            locale           text NOT NULL DEFAULT 'he',
            status           text NOT NULL DEFAULT 'queued'
                             CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
            error            text,
            attempts         integer NOT NULL DEFAULT 0,
            sent_at          timestamptz,
            unsubscribed_at  timestamptz,
            created_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (announcement_id, channel, person_key)
        )
    """)
    op.execute(
        "CREATE INDEX announcement_deliveries_queue"
        " ON app.announcement_deliveries (status, channel)"
    )
    for index, columns in (
        ("announcement_deliveries_user", "user_id"),
        ("announcement_deliveries_tenant", "tenant_id"),
        ("announcement_deliveries_client", "client_id"),
    ):
        op.execute(f"CREATE INDEX {index} ON app.announcement_deliveries ({columns})")
    op.execute("CREATE INDEX announcements_tenant ON app.announcements (tenant_id)")
    op.execute("""
        CREATE TABLE app.announcement_views (
            announcement_id  uuid NOT NULL REFERENCES app.announcements (id) ON DELETE CASCADE,
            user_id          uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            first_viewed_at  timestamptz,
            dismissed_at     timestamptz,
            clicked_at       timestamptz,
            PRIMARY KEY (announcement_id, user_id)
        )
    """)

    op.execute("CREATE INDEX announcement_views_user ON app.announcement_views (user_id)")

    # MyBiz's own tables: no API access at all (RLS with no policy); the console reads and
    # writes them through the SECURITY DEFINER functions below, each checking the permission.
    for table in ("announcements", "announcement_deliveries", "announcement_views"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")

    # Who receives it: one row per person. `audience` = {"groups": ["team", "owners", "staff",
    # "clients"], "verticals": [], "locales": [], "business_ids": [], "modules": [],
    # "status": "trial" | "active" | null}. The filters narrow the businesses; the team group is
    # not tied to a business. Not callable by the API.
    op.execute("""
        CREATE FUNCTION app.announcement_recipients(p_audience jsonb, p_kind text)
        RETURNS TABLE (person_key text, email text, phone text, user_id uuid, client_id uuid,
                       tenant_id uuid, locale text, groups text[], has_push boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            WITH a AS (
                SELECT ARRAY(SELECT jsonb_array_elements_text(
                           coalesce(p_audience -> 'groups', '[]'))) AS groups,
                       ARRAY(SELECT jsonb_array_elements_text(
                           coalesce(p_audience -> 'verticals', '[]'))) AS verticals,
                       ARRAY(SELECT jsonb_array_elements_text(
                           coalesce(p_audience -> 'locales', '[]'))) AS locales,
                       ARRAY(SELECT jsonb_array_elements_text(
                           coalesce(p_audience -> 'business_ids', '[]')))::uuid[] AS ids,
                       ARRAY(SELECT jsonb_array_elements_text(
                           coalesce(p_audience -> 'modules', '[]'))) AS modules,
                       nullif(p_audience ->> 'status', '') AS status
            ),
            biz AS (
                SELECT t.id, t.locale FROM app.tenants t, a
                WHERE t.closed_at IS NULL
                  AND (cardinality(a.verticals) = 0 OR t.vertical = ANY (a.verticals))
                  AND (cardinality(a.locales) = 0 OR t.locale = ANY (a.locales))
                  AND (cardinality(a.ids) = 0 OR t.id = ANY (a.ids))
                  AND (a.status IS NULL
                       OR (a.status = 'trial') = (t.trial_ends_at > now()))
                  AND (cardinality(a.modules) = 0 OR EXISTS (
                        SELECT 1 FROM app.tenant_modules m
                        WHERE m.tenant_id = t.id AND m.module_key = ANY (a.modules)))
            ),
            people AS (
                SELECT 'team'::text AS grp, lower(s.email) AS email, NULL::text AS phone,
                       u.id AS user_id, NULL::uuid AS client_id, NULL::uuid AS tenant_id,
                       coalesce(u.locale, 'he') AS locale
                FROM app.platform_staff s
                CROSS JOIN a
                LEFT JOIN app.users u ON lower(u.email) = s.email
                WHERE NOT s.disabled AND 'team' = ANY (a.groups)
              UNION ALL
                SELECT CASE WHEN m.role = 'owner' THEN 'owners' ELSE 'staff' END,
                       lower(u.email), NULL, u.id, NULL, m.tenant_id, coalesce(u.locale, b.locale)
                FROM app.tenant_members m
                CROSS JOIN a
                JOIN biz b ON b.id = m.tenant_id
                JOIN app.users u ON u.id = m.user_id
                WHERE (CASE WHEN m.role = 'owner' THEN 'owners' ELSE 'staff' END)
                      = ANY (a.groups)
                  AND (p_kind <> 'marketing' OR u.marketing_consent_at IS NOT NULL)
              UNION ALL
                SELECT 'clients', lower(c.email), c.phone, c.user_id, c.id, c.tenant_id,
                       coalesce(u.locale, b.locale)
                FROM app.clients c
                CROSS JOIN a
                JOIN biz b ON b.id = c.tenant_id
                LEFT JOIN app.users u ON u.id = c.user_id
                WHERE c.erased_at IS NULL AND c.status <> 'lead'
                  AND 'clients' = ANY (a.groups)
                  AND (p_kind <> 'marketing'
                       OR c.marketing_consent_at IS NOT NULL
                       OR u.marketing_consent_at IS NOT NULL)
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
                   bool_or(EXISTS (SELECT 1 FROM app.push_tokens pt WHERE pt.user_id = k.user_id))
            FROM keyed k
            GROUP BY k.pkey
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.announcement_recipients(jsonb, text) FROM PUBLIC")

    # The live recipient count for the console, per audience and per channel.
    op.execute("""
        CREATE FUNCTION app.announcement_preview(p_audience jsonb, p_kind text)
        RETURNS jsonb
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_result jsonb;
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            SELECT jsonb_build_object(
                'total', count(*),
                'email', count(*) FILTER (WHERE r.email IS NOT NULL),
                'push', count(*) FILTER (WHERE r.has_push),
                'popup', count(*) FILTER (WHERE r.user_id IS NOT NULL),
                'phone', count(*) FILTER (WHERE r.phone IS NOT NULL AND r.client_id IS NOT NULL),
                'by_group', coalesce((
                    SELECT jsonb_object_agg(g.grp, g.people) FROM (
                        SELECT x.grp, count(*) AS people
                        FROM app.announcement_recipients(p_audience, p_kind) q,
                             unnest(q.groups) AS x(grp)
                        GROUP BY x.grp) g), '{}'))
            INTO v_result
            FROM app.announcement_recipients(p_audience, p_kind) r;
            RETURN v_result;
        END
        $$
    """)

    # The console's reads and writes. Business rules raise P0001 (a message the API maps to 422),
    # P0002 is "not found", P0003 "already sent" (409), 42501 "forbidden".
    op.execute("""
        CREATE FUNCTION app.announcement_rows(p_id uuid)
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
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_save(
            p_id uuid, p_kind text, p_channels text[], p_audience jsonb, p_content jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF p_id IS NULL THEN
                INSERT INTO app.announcements (kind, channels, audience, content, created_by)
                VALUES (p_kind, p_channels, p_audience, p_content,
                        (SELECT m.email FROM app.platform_me() m))
                RETURNING announcements.id INTO v_id;
                RETURN v_id;
            END IF;
            -- A changed message is a draft again, so it is checked again before it is scheduled.
            UPDATE app.announcements a
            SET kind = p_kind, channels = p_channels, audience = p_audience, content = p_content,
                status = 'draft', scheduled_at = NULL, updated_at = now()
            WHERE a.id = p_id AND a.status IN ('draft', 'scheduled')
            RETURNING a.id INTO v_id;
            IF v_id IS NULL THEN
                PERFORM app.announcement_missing(p_id);
            END IF;
            RETURN v_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_missing(p_id uuid) RETURNS void
        LANGUAGE plpgsql STABLE SET search_path = ''
        AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM app.announcements a WHERE a.id = p_id) THEN
                RAISE EXCEPTION 'already_sent' USING ERRCODE = 'P0003';
            END IF;
            RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_schedule(p_id uuid, p_at timestamptz) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.announcements a
            SET status = 'scheduled', scheduled_at = coalesce(p_at, now()), updated_at = now()
            WHERE a.id = p_id AND a.status IN ('draft', 'scheduled');
            IF NOT FOUND THEN
                PERFORM app.announcement_missing(p_id);
            END IF;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_cancel(p_id uuid) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.announcements a SET status = 'cancelled', updated_at = now()
            WHERE a.id = p_id AND a.status IN ('draft', 'scheduled');
            IF NOT FOUND THEN
                PERFORM app.announcement_missing(p_id);
            END IF;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_delete(p_id uuid) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            DELETE FROM app.announcements a
            WHERE a.id = p_id AND a.status IN ('draft', 'cancelled');
            IF NOT FOUND THEN
                PERFORM app.announcement_missing(p_id);
            END IF;
        END
        $$
    """)

    # The pop-up inbox of the signed-in person, and their reactions to it.
    op.execute("""
        CREATE FUNCTION app.my_announcements()
        RETURNS TABLE (id uuid, kind text, content jsonb, locale text, sent_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT a.id, a.kind, a.content, d.locale, a.sent_at
            FROM app.announcement_deliveries d
            JOIN app.announcements a ON a.id = d.announcement_id
            LEFT JOIN app.announcement_views v
                   ON v.announcement_id = a.id AND v.user_id = d.user_id
            WHERE d.channel = 'popup' AND d.user_id = app.current_user_id()
              AND a.status IN ('sending', 'sent') AND v.dismissed_at IS NULL
            ORDER BY a.sent_at DESC NULLS LAST
            LIMIT 20
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.announcement_mark(p_id uuid, p_event text) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user uuid := app.current_user_id();
        BEGIN
            IF p_event NOT IN ('viewed', 'dismissed', 'clicked') THEN
                RAISE EXCEPTION 'unknown_event' USING ERRCODE = 'P0001';
            END IF;
            IF v_user IS NULL OR NOT EXISTS (
                SELECT 1 FROM app.announcement_deliveries d
                WHERE d.announcement_id = p_id AND d.channel = 'popup' AND d.user_id = v_user
            ) THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            INSERT INTO app.announcement_views (announcement_id, user_id, first_viewed_at,
                                                dismissed_at, clicked_at)
            VALUES (p_id, v_user, now(),
                    CASE WHEN p_event = 'dismissed' THEN now() END,
                    CASE WHEN p_event = 'clicked' THEN now() END)
            ON CONFLICT (announcement_id, user_id) DO UPDATE
                SET dismissed_at = CASE WHEN p_event = 'dismissed'
                                        THEN coalesce(app.announcement_views.dismissed_at, now())
                                        ELSE app.announcement_views.dismissed_at END,
                    clicked_at = CASE WHEN p_event = 'clicked'
                                      THEN coalesce(app.announcement_views.clicked_at, now())
                                      ELSE app.announcement_views.clicked_at END;
        END
        $$
    """)

    # Consent: the signed-in person turns marketing messages on or off for their account and
    # their client records.
    op.execute("""
        CREATE FUNCTION app.set_marketing_consent(p_consent boolean) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user uuid := app.current_user_id();
            v_at timestamptz := CASE WHEN p_consent THEN now() END;
        BEGIN
            IF v_user IS NULL THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.users SET marketing_consent_at = v_at WHERE id = v_user;
            UPDATE app.clients SET marketing_consent_at = v_at WHERE user_id = v_user;
        END
        $$
    """)
    # The opt-out link at the foot of every marketing email (no sign-in; the link is signed).
    op.execute("""
        CREATE FUNCTION app.marketing_unsubscribe(p_email text, p_announcement uuid) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_email text := lower(trim(p_email));
        BEGIN
            UPDATE app.users SET marketing_consent_at = NULL
            WHERE lower(email) = v_email AND marketing_consent_at IS NOT NULL;
            UPDATE app.clients SET marketing_consent_at = NULL
            WHERE lower(email) = v_email AND marketing_consent_at IS NOT NULL;
            IF p_announcement IS NOT NULL THEN
                UPDATE app.announcement_deliveries SET unsubscribed_at = now()
                WHERE announcement_id = p_announcement AND lower(email) = v_email
                  AND unsubscribed_at IS NULL;
            END IF;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.announcement_missing(uuid) FROM PUBLIC")
    for function in (
        "announcement_rows(uuid)",
        "announcement_save(uuid, text, text[], jsonb, jsonb)",
        "announcement_schedule(uuid, timestamptz)",
        "announcement_cancel(uuid)",
        "announcement_delete(uuid)",
        "announcement_preview(jsonb, text)",
        "my_announcements()",
        "announcement_mark(uuid, text)",
        "set_marketing_consent(boolean)",
        "marketing_unsubscribe(text, uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in (
        "announcement_delete(uuid)",
        "announcement_cancel(uuid)",
        "announcement_schedule(uuid, timestamptz)",
        "announcement_save(uuid, text, text[], jsonb, jsonb)",
        "announcement_missing(uuid)",
        "announcement_rows(uuid)",
        "marketing_unsubscribe(text, uuid)",
        "set_marketing_consent(boolean)",
        "announcement_mark(uuid, text)",
        "my_announcements()",
        "announcement_preview(jsonb, text)",
        "announcement_recipients(jsonb, text)",
    ):
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.announcement_views")
    op.execute("DROP TABLE app.announcement_deliveries")
    op.execute("DROP TABLE app.announcements")
    op.execute("ALTER TABLE app.clients DROP COLUMN marketing_consent_at")
    op.execute("ALTER TABLE app.users DROP COLUMN marketing_consent_at")
    op.execute(
        "UPDATE app.platform_staff SET permissions = array_remove(permissions, 'broadcasts.manage')"
    )
    op.execute("ALTER TABLE app.platform_staff DROP CONSTRAINT platform_staff_permissions_check")
    op.execute(f"""
        ALTER TABLE app.platform_staff ADD CONSTRAINT platform_staff_permissions_check
        CHECK (permissions <@ ARRAY{list(OLD_PERMISSIONS)}::text[])
    """)
    op.execute(_me(OLD_PERMISSIONS))
