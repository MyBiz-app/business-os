"""Marketing consent as an audit trail, and a one-click opt-out link per client (go-live, GL9).

`consent_events` keeps who agreed to (or withdrew) marketing messages, when, and from where
(the app, the front desk, the opt-out link). The current state stays on the person
(`marketing_consent_at`), with its source next to it. An opt-out from one business's message
(`marketing_opted_out_at`) only affects that business; agreeing again clears it.

Revision ID: 0115
Revises: 0114
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0115"
down_revision: str | None = "0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = (
    "'app_join', 'app_profile', 'desk_signed', 'desk_verbal', 'desk_other', "
    "'unsubscribe_link', 'unsubscribe_email'"
)


RECIPIENTS = """
        CREATE OR REPLACE FUNCTION app.tenant_announcement_recipients(
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
@@RULE@@              UNION ALL
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
"""

NEW_RULE = """
                  AND (p_kind <> 'marketing'
                       OR (c.marketing_opted_out_at IS NULL
                           AND (c.marketing_consent_at IS NOT NULL
                                OR u.marketing_consent_at IS NOT NULL)))
"""
OLD_RULE = """
                  AND (p_kind <> 'marketing'
                       OR c.marketing_consent_at IS NOT NULL
                       OR u.marketing_consent_at IS NOT NULL)
"""


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.clients
            ADD COLUMN marketing_consent_source text,
            ADD COLUMN marketing_opted_out_at timestamptz,
            ADD COLUMN unsubscribe_token text NOT NULL
                DEFAULT substr(replace(gen_random_uuid()::text, '-', ''), 1, 20)
    """)
    op.execute("CREATE UNIQUE INDEX clients_unsubscribe_token ON app.clients (unsubscribe_token)")
    op.execute("ALTER TABLE app.users ADD COLUMN marketing_consent_source text")
    op.execute(f"""
        CREATE TABLE app.consent_events (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid REFERENCES app.clients (id) ON DELETE CASCADE,
            user_id     uuid REFERENCES app.users (id) ON DELETE CASCADE,
            action      text NOT NULL CHECK (action IN ('granted', 'withdrawn')),
            channel     text NOT NULL DEFAULT 'marketing' CHECK (channel = 'marketing'),
            source      text NOT NULL CHECK (source IN ({SOURCES})),
            recorded_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            ip          text,
            user_agent  text,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX consent_events_tenant ON app.consent_events (tenant_id, created_at)")
    op.execute("CREATE INDEX consent_events_client_fk ON app.consent_events (client_id)")
    op.execute("CREATE INDEX consent_events_user_fk ON app.consent_events (user_id)")
    op.execute("CREATE INDEX consent_events_recorded_by_fk ON app.consent_events (recorded_by)")
    # Written only by the functions below; a business reads its own clients' trail.
    op.execute("GRANT SELECT ON app.consent_events TO app_api")
    op.execute("ALTER TABLE app.consent_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY consent_events_tenant ON app.consent_events TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)

    # One client's state changed: update the row and add the event (nothing if it did not change).
    op.execute("""
        CREATE FUNCTION app.apply_client_consent(
            p_client uuid, p_consent boolean, p_source text, p_ip text, p_user_agent text
        ) RETURNS boolean
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_row app.clients%ROWTYPE;
        BEGIN
            SELECT * INTO v_row FROM app.clients WHERE id = p_client FOR UPDATE;
            IF NOT FOUND OR (v_row.marketing_consent_at IS NOT NULL) = p_consent THEN
                RETURN false;
            END IF;
            UPDATE app.clients
            SET marketing_consent_at = CASE WHEN p_consent THEN now() END,
                marketing_consent_source = p_source,
                marketing_opted_out_at = CASE WHEN p_consent THEN NULL ELSE now() END
            WHERE id = p_client;
            INSERT INTO app.consent_events
                (tenant_id, client_id, user_id, action, source, recorded_by, ip, user_agent)
            VALUES (v_row.tenant_id, p_client, v_row.user_id,
                    CASE WHEN p_consent THEN 'granted' ELSE 'withdrawn' END,
                    p_source, app.current_user_id(), p_ip, p_user_agent);
            RETURN true;
        END
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app.apply_client_consent(uuid, boolean, text, text, text) "
        "FROM PUBLIC"
    )

    # The front desk records (or withdraws) a client's consent, only inside the current business.
    op.execute("""
        CREATE FUNCTION app.set_client_consent(
            p_client uuid, p_consent boolean, p_source text, p_ip text, p_user_agent text
        ) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM app.clients
                           WHERE id = p_client AND tenant_id = app.current_tenant_id()) THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            PERFORM app.apply_client_consent(p_client, p_consent, p_source, p_ip, p_user_agent);
        END
        $$
    """)

    # The signed-in person turns marketing on or off for their account and every client record.
    op.execute("DROP FUNCTION app.set_marketing_consent(boolean)")
    op.execute("""
        CREATE FUNCTION app.set_marketing_consent(
            p_consent boolean, p_source text, p_ip text, p_user_agent text
        ) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user uuid := app.current_user_id();
            v_client uuid;
        BEGIN
            IF v_user IS NULL THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF EXISTS (SELECT 1 FROM app.users
                       WHERE id = v_user AND (marketing_consent_at IS NOT NULL) <> p_consent) THEN
                UPDATE app.users
                SET marketing_consent_at = CASE WHEN p_consent THEN now() END,
                    marketing_consent_source = p_source
                WHERE id = v_user;
                INSERT INTO app.consent_events
                    (user_id, action, source, recorded_by, ip, user_agent)
                VALUES (v_user, CASE WHEN p_consent THEN 'granted' ELSE 'withdrawn' END,
                        p_source, v_user, p_ip, p_user_agent);
            END IF;
            FOR v_client IN SELECT id FROM app.clients WHERE user_id = v_user LOOP
                PERFORM app.apply_client_consent(v_client, p_consent, p_source, p_ip, p_user_agent);
            END LOOP;
        END
        $$
    """)

    # The opt-out link of a marketing email: every record with that address.
    op.execute("DROP FUNCTION app.marketing_unsubscribe(text, uuid)")
    op.execute("""
        CREATE FUNCTION app.marketing_unsubscribe(p_email text, p_announcement uuid)
        RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_email text := lower(trim(p_email));
            v_id uuid;
        BEGIN
            FOR v_id IN SELECT id FROM app.users
                        WHERE lower(email) = v_email AND marketing_consent_at IS NOT NULL LOOP
                UPDATE app.users SET marketing_consent_at = NULL,
                    marketing_consent_source = 'unsubscribe_email' WHERE id = v_id;
                INSERT INTO app.consent_events (user_id, action, source, ip)
                VALUES (v_id, 'withdrawn', 'unsubscribe_email', NULL);
            END LOOP;
            FOR v_id IN SELECT id FROM app.clients
                        WHERE lower(email) = v_email AND marketing_consent_at IS NOT NULL LOOP
                PERFORM app.apply_client_consent(v_id, false, 'unsubscribe_email', NULL, NULL);
            END LOOP;
            IF p_announcement IS NOT NULL THEN
                UPDATE app.announcement_deliveries SET unsubscribed_at = now()
                WHERE announcement_id = p_announcement AND lower(email) = v_email
                  AND unsubscribed_at IS NULL;
            END IF;
        END
        $$
    """)

    # The short link in an SMS / WhatsApp / email (/u/<token>): opts that client out of this
    # business's ads. Returns the business name, or null when the token is unknown.
    op.execute("""
        CREATE FUNCTION app.unsubscribe_by_token(p_token text, p_ip text, p_user_agent text)
        RETURNS text
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
            v_name text;
        BEGIN
            SELECT c.id, t.name INTO v_id, v_name
            FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
            WHERE c.unsubscribe_token = p_token;
            IF v_id IS NULL THEN
                RETURN NULL;
            END IF;
            IF NOT app.apply_client_consent(
                v_id, false, 'unsubscribe_link', p_ip, p_user_agent
            ) THEN
                -- Already without consent: still record the refusal so an ad is never sent.
                UPDATE app.clients
                SET marketing_opted_out_at = coalesce(marketing_opted_out_at, now())
                WHERE id = v_id;
            END IF;
            RETURN v_name;
        END
        $$
    """)
    for function in (
        "set_client_consent(uuid, boolean, text, text, text)",
        "set_marketing_consent(boolean, text, text, text)",
        "marketing_unsubscribe(text, uuid)",
        "unsubscribe_by_token(text, text, text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")

    # At send time too: someone who opted out after the message was scheduled is skipped.
    op.execute(RECIPIENTS.replace("@@RULE@@", NEW_RULE))

    # Today's agreements get their first event, so the trail starts complete.
    op.execute("""
        INSERT INTO app.consent_events (tenant_id, client_id, user_id, action, source, created_at)
        SELECT tenant_id, id, user_id, 'granted', 'app_profile', marketing_consent_at
        FROM app.clients WHERE marketing_consent_at IS NOT NULL
    """)
    op.execute("""
        INSERT INTO app.consent_events (user_id, action, source, created_at)
        SELECT id, 'granted', 'app_profile', marketing_consent_at
        FROM app.users WHERE marketing_consent_at IS NOT NULL
    """)


def downgrade() -> None:
    op.execute(RECIPIENTS.replace("@@RULE@@", OLD_RULE))
    op.execute("DROP FUNCTION app.unsubscribe_by_token(text, text, text)")
    op.execute("DROP FUNCTION app.marketing_unsubscribe(text, uuid)")
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
    op.execute("GRANT EXECUTE ON FUNCTION app.marketing_unsubscribe(text, uuid) TO app_api")
    op.execute("DROP FUNCTION app.set_marketing_consent(boolean, text, text, text)")
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
    op.execute("GRANT EXECUTE ON FUNCTION app.set_marketing_consent(boolean) TO app_api")
    op.execute("DROP FUNCTION app.set_client_consent(uuid, boolean, text, text, text)")
    op.execute("DROP FUNCTION app.apply_client_consent(uuid, boolean, text, text, text)")
    op.execute("DROP TABLE app.consent_events")
    op.execute("ALTER TABLE app.users DROP COLUMN marketing_consent_source")
    op.execute("""
        ALTER TABLE app.clients
            DROP COLUMN unsubscribe_token,
            DROP COLUMN marketing_opted_out_at,
            DROP COLUMN marketing_consent_source
    """)
