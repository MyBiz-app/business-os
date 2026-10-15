"""Friends inside a business (round 4, B2).

A client finds a friend by a personal code, a QR or the friend's exact phone / email, never by
browsing the client list. Friends can be invited to a class; the invited spot is held (and
counted in the class capacity) until the friend answers or the invite expires.

Everything a client reads about another client goes through SECURITY DEFINER functions that
return only the few fields a friend or fellow participant may see.

Revision ID: 0082
Revises: 0081
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0082"
down_revision: str | None = "0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
    "plan_ending",
)
NEW_KINDS = ("friend_request", "class_invite")

ME = "app.current_client_id()"

# The waitlist promotion of migration 0017, now leaving the spots held by invites free.
PROMOTE = """
    CREATE OR REPLACE FUNCTION app.promote_waitlist(p_session_id uuid) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v_free integer;
        v_promoted integer;
    BEGIN
        SELECT s.capacity - (
            SELECT count(*) FROM app.bookings b
            WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
        ){holds}
        INTO v_free
        FROM app.sessions s
        WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id()
          AND s.status = 'scheduled' AND s.starts_at > now();
        IF coalesce(v_free, 0) <= 0 THEN
            RETURN 0;
        END IF;
        WITH promoted AS (
            UPDATE app.bookings SET status = 'booked', updated_at = now()
            WHERE id IN (
                SELECT b.id FROM app.bookings b
                WHERE b.session_id = p_session_id AND b.status = 'waitlisted'
                ORDER BY b.waitlisted_at, b.id
                LIMIT v_free
            )
            RETURNING id, tenant_id, client_id, session_id
        ),
        notified AS (
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT p.tenant_id, p.client_id, 'waitlist_promoted',
                   jsonb_build_object('session_id', s.id, 'service_name', sv.name,
                                      'starts_at', s.starts_at, 'booking_id', p.id)
            FROM promoted p
            JOIN app.sessions s ON s.id = p.session_id
            JOIN app.services sv ON sv.id = s.service_id
            RETURNING 1
        )
        SELECT count(*) INTO v_promoted FROM promoted;
        RETURN v_promoted;
    END
    $$
"""

HOLDS = (
    " - (SELECT count(*) FROM app.class_invites i"
    " WHERE i.session_id = s.id AND i.status = 'pending' AND i.expires_at > now())"
)


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


def _definer(name: str, signature: str, returns: str, body: str) -> None:
    op.execute(f"""
        CREATE FUNCTION app.{name}({signature}) RETURNS {returns}
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$ {body} $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION app.{name}({_types(signature)}) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app.{name}({_types(signature)}) TO app_api")


def _types(signature: str) -> str:
    return ", ".join(part.split()[1] for part in signature.split(",") if part.strip())


def upgrade() -> None:
    _kinds_check((*KINDS, *NEW_KINDS))

    op.execute("""
        CREATE TABLE app.client_social (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid NOT NULL,
            friend_code text NOT NULL UNIQUE CHECK (length(friend_code) BETWEEN 8 AND 16),
            visible     boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, client_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE app.client_friendships (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            requester_id uuid NOT NULL,
            addressee_id uuid NOT NULL,
            status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
            created_at   timestamptz NOT NULL DEFAULT now(),
            responded_at timestamptz,
            CHECK (requester_id <> addressee_id),
            FOREIGN KEY (tenant_id, requester_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, addressee_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX client_friendships_pair ON app.client_friendships
            (tenant_id, least(requester_id, addressee_id), greatest(requester_id, addressee_id))
    """)
    op.execute(
        "CREATE INDEX client_friendships_requester ON app.client_friendships "
        "(tenant_id, requester_id)"
    )
    op.execute(
        "CREATE INDEX client_friendships_addressee ON app.client_friendships "
        "(tenant_id, addressee_id)"
    )
    op.execute("""
        CREATE TABLE app.class_invites (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            session_id   uuid NOT NULL REFERENCES app.sessions (id) ON DELETE CASCADE,
            inviter_id   uuid NOT NULL,
            invitee_id   uuid NOT NULL,
            status       text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired')),
            expires_at   timestamptz NOT NULL,
            booking_id   uuid,
            created_at   timestamptz NOT NULL DEFAULT now(),
            responded_at timestamptz,
            CHECK (inviter_id <> invitee_id),
            FOREIGN KEY (tenant_id, inviter_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, invitee_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX class_invites_open ON app.class_invites (session_id, invitee_id) "
        "WHERE status = 'pending'"
    )
    op.execute("CREATE INDEX class_invites_invitee ON app.class_invites (tenant_id, invitee_id)")
    op.execute("CREATE INDEX class_invites_inviter ON app.class_invites (tenant_id, inviter_id)")

    for table, grant in (
        ("client_social", "SELECT, INSERT, UPDATE"),
        ("client_friendships", "SELECT, INSERT, UPDATE, DELETE"),
        ("class_invites", "SELECT, INSERT, UPDATE"),
    ):
        op.execute(f"GRANT {grant} ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        # Staff may read them (the business owns the data); only the clients write.
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} FOR SELECT TO app_api
            USING (tenant_id = app.current_tenant_id())
        """)
    op.execute(f"""
        CREATE POLICY client_social_client ON app.client_social TO app_api
        USING (client_id = {ME})
        WITH CHECK (client_id = {ME} AND tenant_id = app.client_tenant_id())
    """)
    op.execute(f"""
        CREATE POLICY client_friendships_select ON app.client_friendships FOR SELECT TO app_api
        USING (requester_id = {ME} OR addressee_id = {ME})
    """)
    op.execute(f"""
        CREATE POLICY client_friendships_insert ON app.client_friendships FOR INSERT TO app_api
        WITH CHECK (requester_id = {ME} AND tenant_id = app.client_tenant_id())
    """)
    op.execute(f"""
        CREATE POLICY client_friendships_update ON app.client_friendships FOR UPDATE TO app_api
        USING (addressee_id = {ME}) WITH CHECK (addressee_id = {ME})
    """)
    op.execute(f"""
        CREATE POLICY client_friendships_delete ON app.client_friendships FOR DELETE TO app_api
        USING (requester_id = {ME} OR addressee_id = {ME})
    """)
    op.execute(f"""
        CREATE POLICY class_invites_select ON app.class_invites FOR SELECT TO app_api
        USING (inviter_id = {ME} OR invitee_id = {ME})
    """)
    op.execute(f"""
        CREATE POLICY class_invites_insert ON app.class_invites FOR INSERT TO app_api
        WITH CHECK (inviter_id = {ME} AND tenant_id = app.client_tenant_id())
    """)
    op.execute(f"""
        CREATE POLICY class_invites_update ON app.class_invites FOR UPDATE TO app_api
        USING (inviter_id = {ME} OR invitee_id = {ME})
        WITH CHECK (inviter_id = {ME} OR invitee_id = {ME})
    """)

    # Invited spots count as taken until the invite is answered or expires.
    op.execute("""
        CREATE OR REPLACE FUNCTION app.session_counts(p_session_id uuid)
        RETURNS TABLE (booked integer, waitlisted integer)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT count(*) FILTER (WHERE b.status IN ('booked', 'checked_in', 'no_show'))::int
                   + (SELECT count(*)::int FROM app.class_invites i
                      WHERE i.session_id = p_session_id AND i.tenant_id = app.acting_tenant_id()
                        AND i.status = 'pending' AND i.expires_at > now()),
                   count(*) FILTER (WHERE b.status = 'waitlisted')::int
            FROM app.bookings b
            WHERE b.session_id = p_session_id AND b.tenant_id = app.acting_tenant_id()
        $$
    """)
    op.execute(PROMOTE.format(holds=HOLDS))

    # --- What one client may know about another -------------------------------------------
    scope = f"""(
        (SELECT t.network_scope FROM app.tenants t WHERE t.id = app.client_tenant_id())
            = 'network'
        OR EXISTS (
            SELECT 1 FROM app.client_locations mine
            JOIN app.client_locations theirs
              ON theirs.tenant_id = mine.tenant_id AND theirs.location_id = mine.location_id
            WHERE mine.client_id = {ME} AND theirs.client_id = p_client
        )
    )"""
    _definer(
        "social_in_scope",
        "p_client uuid",
        "boolean",
        f"SELECT {scope} AND EXISTS (SELECT 1 FROM app.clients c WHERE c.id = p_client "
        "AND c.tenant_id = app.client_tenant_id() AND c.erased_at IS NULL "
        "AND c.user_id IS NOT NULL)",
    )
    _definer(
        "social_find",
        "p_code text, p_phone text, p_email text",
        "uuid",
        f"""
        SELECT c.id FROM app.clients c
        LEFT JOIN app.client_social s ON s.client_id = c.id
        WHERE c.tenant_id = app.client_tenant_id() AND c.id <> {ME}
          AND app.social_in_scope(c.id)
          AND ((p_code IS NOT NULL AND s.friend_code = p_code)
            OR (p_phone IS NOT NULL AND length(p_phone) >= 7
                AND right(regexp_replace(c.phone, '\\D', '', 'g'), 9) = right(p_phone, 9))
            OR (p_email IS NOT NULL AND lower(c.email) = lower(p_email)))
        ORDER BY c.created_at LIMIT 1
        """,
    )
    # A person's card: the friend sees the full name, a fellow participant the first name only.
    card = f"""
        SELECT c.id AS client_id, c.first_name,
               CASE WHEN f.status = 'accepted' THEN c.last_name END AS last_name,
               u.status_text, u.avatar_updated_at,
               CASE WHEN f.id IS NULL THEN 'none'
                    WHEN f.status = 'accepted' THEN 'friends'
                    WHEN f.requester_id = {ME} THEN 'request_sent'
                    ELSE 'request_received' END AS friendship,
               f.id AS friendship_id,
               CASE WHEN f.status = 'accepted' THEN f.responded_at END AS friends_since,
               (SELECT count(*)::int
                FROM app.bookings mine
                JOIN app.bookings theirs ON theirs.session_id = mine.session_id
                JOIN app.sessions s ON s.id = mine.session_id
                WHERE mine.client_id = {ME} AND theirs.client_id = c.id
                  AND mine.dependent_id IS NULL AND theirs.dependent_id IS NULL
                  AND s.status = 'scheduled'
                  AND mine.status IN ('booked', 'checked_in')
                  AND theirs.status IN ('booked', 'checked_in')
                  AND (s.ends_at < now() OR (mine.status = 'checked_in'
                                             AND theirs.status = 'checked_in'))
               ) AS together
        FROM app.clients c
        LEFT JOIN app.users u ON u.id = c.user_id
        LEFT JOIN app.client_friendships f
               ON f.tenant_id = c.tenant_id
              AND least(f.requester_id, f.addressee_id) = least(c.id, {ME})
              AND greatest(f.requester_id, f.addressee_id) = greatest(c.id, {ME})
        LEFT JOIN app.client_social cs ON cs.client_id = c.id
    """
    card_columns = (
        "client_id uuid, first_name text, last_name text, status_text text, "
        "avatar_updated_at timestamptz, friendship text, friendship_id uuid, "
        "friends_since timestamptz, together integer"
    )
    # Someone I know: a friend, or a pending request either way.
    op.execute(f"""
        CREATE FUNCTION app.social_connections()
        RETURNS TABLE ({card_columns})
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$ {card}
            WHERE c.tenant_id = app.client_tenant_id() AND f.id IS NOT NULL
              AND c.erased_at IS NULL
        $$
    """)
    # Fellow participants of a session who agreed to be listed (friends are always listed).
    op.execute(f"""
        CREATE FUNCTION app.social_participants(p_session uuid)
        RETURNS TABLE ({card_columns})
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$ {card}
            WHERE c.tenant_id = app.client_tenant_id() AND c.id <> {ME}
              AND c.erased_at IS NULL AND c.user_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM app.bookings b
                          WHERE b.session_id = p_session AND b.client_id = c.id
                            AND b.dependent_id IS NULL
                            AND b.status IN ('booked', 'checked_in', 'no_show'))
              AND (f.status = 'accepted' OR coalesce(cs.visible, true))
        $$
    """)
    # One person met in a class (or a friend / pending request): never anyone else.
    op.execute(f"""
        CREATE FUNCTION app.social_person(p_client uuid)
        RETURNS TABLE ({card_columns})
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$ {card}
            WHERE c.id = p_client AND c.tenant_id = app.client_tenant_id()
              AND c.id <> {ME} AND c.erased_at IS NULL AND c.user_id IS NOT NULL
              AND (f.id IS NOT NULL OR (coalesce(cs.visible, true) AND EXISTS (
                    SELECT 1 FROM app.bookings mine
                    JOIN app.bookings theirs ON theirs.session_id = mine.session_id
                    WHERE mine.client_id = {ME} AND theirs.client_id = c.id
                      AND mine.dependent_id IS NULL AND theirs.dependent_id IS NULL
                      AND mine.status <> 'cancelled' AND theirs.status <> 'cancelled')))
        $$
    """)
    # Where those shared classes were (the catalog decides per branch whether lists exist).
    _definer(
        "social_shared_locations",
        "p_client uuid",
        "TABLE (location_id uuid)",
        f"""
        SELECT DISTINCT s.location_id
        FROM app.bookings mine
        JOIN app.bookings theirs ON theirs.session_id = mine.session_id
        JOIN app.sessions s ON s.id = mine.session_id
        WHERE mine.client_id = {ME} AND theirs.client_id = p_client
          AND mine.status <> 'cancelled' AND theirs.status <> 'cancelled'
        """,
    )
    _definer(
        "social_together_by_service",
        "p_client uuid",
        "TABLE (service_id uuid, service_name text, together integer)",
        f"""
        SELECT sv.id, sv.name, count(*)::int
        FROM app.bookings mine
        JOIN app.bookings theirs ON theirs.session_id = mine.session_id
        JOIN app.sessions s ON s.id = mine.session_id
        JOIN app.services sv ON sv.id = s.service_id
        WHERE mine.client_id = {ME} AND theirs.client_id = p_client
          AND mine.dependent_id IS NULL AND theirs.dependent_id IS NULL
          AND s.status = 'scheduled'
          AND mine.status IN ('booked', 'checked_in') AND theirs.status IN ('booked', 'checked_in')
          AND (s.ends_at < now() OR (mine.status = 'checked_in' AND theirs.status = 'checked_in'))
        GROUP BY sv.id, sv.name ORDER BY count(*) DESC, sv.name
        """,
    )
    _definer(
        "social_has_booking",
        "p_client uuid, p_session uuid",
        "boolean",
        """
        SELECT app.social_in_scope(p_client) AND EXISTS (
            SELECT 1 FROM app.bookings b
            WHERE b.session_id = p_session AND b.client_id = p_client
              AND b.dependent_id IS NULL AND b.status <> 'cancelled')
        """,
    )
    _definer(
        "social_avatar",
        "p_client uuid",
        "TABLE (avatar bytea, content_type text)",
        """
        SELECT u.avatar, u.avatar_content_type
        FROM app.social_person(p_client) p
        JOIN app.clients c ON c.id = p.client_id
        JOIN app.users u ON u.id = c.user_id
        WHERE u.avatar IS NOT NULL
        """,
    )
    op.execute("""
        CREATE FUNCTION app.social_notify(p_client uuid, p_kind text, p_payload jsonb)
        RETURNS void
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT app.client_tenant_id(), p_client, p_kind, p_payload
            WHERE p_kind IN ('friend_request', 'class_invite')
              AND app.social_in_scope(p_client)
        $$
    """)
    for signature in (
        "app.social_connections()",
        "app.social_participants(uuid)",
        "app.social_person(uuid)",
        "app.social_notify(uuid, text, jsonb)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")


def downgrade() -> None:
    for signature in (
        "app.social_notify(uuid, text, jsonb)",
        "app.social_avatar(uuid)",
        "app.social_has_booking(uuid, uuid)",
        "app.social_together_by_service(uuid)",
        "app.social_shared_locations(uuid)",
        "app.social_person(uuid)",
        "app.social_participants(uuid)",
        "app.social_connections()",
        "app.social_find(text, text, text)",
        "app.social_in_scope(uuid)",
    ):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(PROMOTE.format(holds=""))
    op.execute("""
        CREATE OR REPLACE FUNCTION app.session_counts(p_session_id uuid)
        RETURNS TABLE (booked integer, waitlisted integer)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT count(*) FILTER (WHERE b.status IN ('booked', 'checked_in', 'no_show'))::int,
                   count(*) FILTER (WHERE b.status = 'waitlisted')::int
            FROM app.bookings b
            WHERE b.session_id = p_session_id AND b.tenant_id = app.acting_tenant_id()
        $$
    """)
    op.execute("DROP TABLE app.class_invites")
    op.execute("DROP TABLE app.client_friendships")
    op.execute("DROP TABLE app.client_social")
    op.execute("DELETE FROM app.notifications WHERE kind IN ('friend_request', 'class_invite')")
    _kinds_check(KINDS)
