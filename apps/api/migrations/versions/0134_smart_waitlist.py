"""Smart waitlist: requests for a time range, a whole day, an appointment or a court (round 7, R30).

Expand step, nothing is dropped or retyped, so the previous release keeps working:

- `tenants` gets the switch and the working mode per kind (classes, appointments, resources) and the
  hours before a class when "sign up automatically" turns into "first to grab it".
  Existing businesses keep today's behaviour for classes (`auto`); appointments and resources start
  off. `services.waitlist_mode` overrides the business setting for one service.
- `waitlist_requests`: what a client waits for (a given time, a time range or a whole day).
- `waitlist_offers`: who was told about which free spot, so nobody is told twice and the others
  are told when someone else took it.
- `app.promote_waitlist` only promotes automatically when the mode is `auto` and the class is
  further away than the cut-off; closer in (or in the other modes) the spot is offered instead.
- Two SECURITY DEFINER functions find the waiting clients and tell them (the client who cancels
  cannot read other clients' rows), like `promote_waitlist` always did.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0134"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = (
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
    "plan_ending",
    "friend_request",
    "class_invite",
)
NEW_KINDS = ("waitlist_spot_open", "waitlist_spot_taken")

MODES = "('off', 'auto', 'first_come', 'manual')"

HOLDS = (
    " - (SELECT count(*) FROM app.class_invites i"
    " WHERE i.session_id = s.id AND i.status = 'pending' AND i.expires_at > now())"
)

MODE_FOR = """
    CREATE FUNCTION app.waitlist_mode_for(p_service uuid) RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
    AS $$
        SELECT CASE WHEN NOT t.waitlist_enabled THEN 'off'
                    ELSE coalesce(sv.waitlist_mode,
                                  CASE sv.booking_mode WHEN 'class' THEN t.waitlist_class_mode
                                       WHEN 'appointment' THEN t.waitlist_appointment_mode
                                       ELSE t.waitlist_resource_mode END)
               END
        FROM app.services sv JOIN app.tenants t ON t.id = sv.tenant_id
        WHERE sv.id = p_service AND sv.tenant_id = app.acting_tenant_id()
    $$
"""

# A class has a free spot while it has capacity left (invites hold spots); a personal appointment
# or a court is free while nothing live overlaps it for the same person or room.
SLOT_IS_FREE = (
    """
    CREATE FUNCTION app.waitlist_slot_is_free(p_session_id uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
    AS $$
        SELECT s.starts_at > now() AND CASE WHEN sv.booking_mode = 'class' THEN
            s.status = 'scheduled' AND s.capacity - (
                SELECT count(*) FROM app.bookings b
                WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
            )"""
    + HOLDS
    + """ > 0
        ELSE NOT EXISTS (
            SELECT 1 FROM app.sessions o JOIN app.services ov ON ov.id = o.service_id
            WHERE o.tenant_id = s.tenant_id AND o.status = 'scheduled'
              AND o.starts_at - make_interval(mins => o.travel_minutes)
                  < s.ends_at AND o.ends_at > s.starts_at - make_interval(mins => s.travel_minutes)
              AND ((s.room_id IS NOT NULL AND o.room_id = s.room_id)
                   OR (s.instructor_user_id IS NOT NULL
                       AND o.instructor_user_id = s.instructor_user_id))
              AND (ov.booking_mode = 'class' OR EXISTS (
                  SELECT 1 FROM app.bookings b
                  WHERE b.session_id = o.id AND b.status IN ('booked', 'checked_in', 'no_show')))
        ) END
        FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
        WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id()
    $$
"""
)

MATCHES = """
    CREATE FUNCTION app.waitlist_matches(p_request uuid, p_session uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
    AS $$
        SELECT r.service_id = s.service_id
           AND (r.staff_user_id IS NULL OR r.staff_user_id = s.instructor_user_id)
           AND (r.location_id IS NULL OR r.location_id = s.location_id)
           AND (r.starts_at IS NULL OR r.starts_at = s.starts_at)
           AND r.day = (s.starts_at AT TIME ZONE t.time_zone)::date
           AND (r.from_time IS NULL
                OR ((s.starts_at AT TIME ZONE t.time_zone)::time >= r.from_time
                    AND (s.starts_at AT TIME ZONE t.time_zone)::time < r.to_time))
        FROM app.waitlist_requests r, app.sessions s, app.tenants t
        WHERE r.id = p_request AND s.id = p_session AND t.id = s.tenant_id
          AND r.tenant_id = s.tenant_id AND s.tenant_id = app.acting_tenant_id()
    $$
"""

ON_FREED = """
    CREATE FUNCTION app.waitlist_on_freed(p_session_id uuid) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v_s record;
        v_mode text;
        v_offered integer := 0;
    BEGIN
        SELECT s.id, s.tenant_id, s.service_id, s.starts_at, s.ends_at, sv.name AS service_name,
               t.waitlist_auto_hours
        INTO v_s
        FROM app.sessions s
        JOIN app.services sv ON sv.id = s.service_id
        JOIN app.tenants t ON t.id = s.tenant_id
        WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id();
        IF NOT FOUND OR v_s.starts_at <= now() THEN
            RETURN 0;
        END IF;
        v_mode := app.waitlist_mode_for(v_s.service_id);
        -- Manual: the team sees the open spot and the waiting list in the CRM and decides.
        IF v_mode NOT IN ('auto', 'first_come') OR NOT app.waitlist_slot_is_free(p_session_id) THEN
            RETURN 0;
        END IF;
        WITH candidates AS (
            SELECT DISTINCT ON (c.client_id) c.client_id, c.request_id, c.booking_id
            FROM (
                SELECT r.client_id, r.id AS request_id, NULL::uuid AS booking_id, r.created_at AS at
                FROM app.waitlist_requests r
                WHERE r.tenant_id = v_s.tenant_id AND r.status IN ('active', 'offered')
                  AND r.expires_at > now() AND app.waitlist_matches(r.id, p_session_id)
                  AND NOT EXISTS (
                      SELECT 1 FROM app.bookings b
                      WHERE b.session_id = p_session_id AND b.client_id = r.client_id
                        AND b.status IN ('booked', 'checked_in', 'no_show'))
                UNION ALL
                -- Someone already on this class's own waitlist; with "automatic" they were
                -- promoted already, unless the class is too close for that.
                SELECT b.client_id, NULL::uuid, b.id, b.waitlisted_at
                FROM app.bookings b
                WHERE b.session_id = p_session_id AND b.status = 'waitlisted'
                  AND (v_mode = 'first_come'
                       OR v_s.starts_at <= now() + make_interval(hours => v_s.waitlist_auto_hours))
            ) c
            ORDER BY c.client_id, c.booking_id NULLS LAST, c.at
        ),
        opened AS (
            INSERT INTO app.waitlist_offers
                (tenant_id, session_id, client_id, request_id, booking_id)
            SELECT v_s.tenant_id, p_session_id, c.client_id, c.request_id, c.booking_id
            FROM candidates c
            ON CONFLICT (session_id, client_id) DO UPDATE
                SET status = 'open', offered_at = now(),
                    request_id = excluded.request_id, booking_id = excluded.booking_id
                WHERE app.waitlist_offers.status <> 'open'
            RETURNING client_id, request_id
        ),
        marked AS (
            UPDATE app.waitlist_requests r
            SET status = 'offered', offered_session_id = p_session_id, offered_at = now(),
                updated_at = now()
            FROM opened o WHERE r.id = o.request_id
            RETURNING r.id
        ),
        told AS (
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT v_s.tenant_id, o.client_id, 'waitlist_spot_open',
                   jsonb_build_object('session_id', p_session_id, 'service_name', v_s.service_name,
                                      'starts_at', v_s.starts_at, 'ends_at', v_s.ends_at)
            FROM opened o
            RETURNING 1
        )
        SELECT count(*) INTO v_offered FROM opened;
        RETURN v_offered;
    END
    $$
"""

ON_BOOKED = """
    CREATE FUNCTION app.waitlist_on_booked(p_session_id uuid, p_client_id uuid) RETURNS void
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v_s record;
    BEGIN
        SELECT s.id, s.tenant_id, s.starts_at, s.ends_at, s.room_id, s.instructor_user_id
        INTO v_s FROM app.sessions s
        WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id();
        IF NOT FOUND THEN
            RETURN;
        END IF;
        -- The client got what they waited for: their matching requests are done.
        UPDATE app.waitlist_requests r SET status = 'fulfilled', updated_at = now()
        WHERE r.tenant_id = v_s.tenant_id AND r.client_id = p_client_id
          AND r.status IN ('active', 'offered') AND app.waitlist_matches(r.id, p_session_id);
        UPDATE app.waitlist_offers o SET status = 'claimed'
        WHERE o.tenant_id = v_s.tenant_id AND o.client_id = p_client_id AND o.status = 'open'
          AND o.session_id = p_session_id;
        -- Everyone else who was told about this spot (or one that overlaps it) is told it is gone.
        WITH gone AS (
            UPDATE app.waitlist_offers o SET status = 'taken'
            FROM app.sessions os
            WHERE os.id = o.session_id AND o.tenant_id = v_s.tenant_id AND o.status = 'open'
              AND o.client_id <> p_client_id
              AND (os.id = v_s.id
                   OR (os.starts_at < v_s.ends_at AND os.ends_at > v_s.starts_at
                       AND (os.instructor_user_id = v_s.instructor_user_id
                            OR os.room_id = v_s.room_id)))
              AND NOT app.waitlist_slot_is_free(o.session_id)
            RETURNING o.client_id, o.request_id, o.session_id
        ),
        reopened AS (
            UPDATE app.waitlist_requests r
            SET status = 'active', offered_session_id = NULL, updated_at = now()
            FROM gone g WHERE r.id = g.request_id AND r.status = 'offered'
            RETURNING r.id
        )
        INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
        SELECT v_s.tenant_id, g.client_id, 'waitlist_spot_taken',
               jsonb_build_object('session_id', g.session_id, 'service_name', sv.name,
                                  'starts_at', gs.starts_at)
        FROM gone g
        JOIN app.sessions gs ON gs.id = g.session_id
        JOIN app.services sv ON sv.id = gs.service_id;
    END
    $$
"""

# The promotion of migration 0082, now only automatic when the business works that way and the
# class is further away than the cut-off; otherwise `waitlist_on_freed` offers the spot.
PROMOTE_TAIL = """
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


def _promote(*, gated: bool) -> str:
    gate = (
        " AND app.waitlist_mode_for(s.service_id) = 'auto'"
        " AND s.starts_at > now() + make_interval(hours => t.waitlist_auto_hours)"
        if gated
        else ""
    )
    tenants = ", app.tenants t" if gated else ""
    tenant_join = " AND t.id = s.tenant_id" if gated else ""
    return f"""
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
        ){HOLDS}
        INTO v_free
        FROM app.sessions s{tenants}
        WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id()
          AND s.status = 'scheduled' AND s.starts_at > now(){tenant_join}{gate};
    {PROMOTE_TAIL}"""


def _definer_grants(signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_api")


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE app.tenants
            ADD COLUMN waitlist_enabled boolean NOT NULL DEFAULT true,
            ADD COLUMN waitlist_class_mode text NOT NULL DEFAULT 'auto'
                CHECK (waitlist_class_mode IN {MODES}),
            ADD COLUMN waitlist_appointment_mode text NOT NULL DEFAULT 'off'
                CHECK (waitlist_appointment_mode IN {MODES}),
            ADD COLUMN waitlist_resource_mode text NOT NULL DEFAULT 'off'
                CHECK (waitlist_resource_mode IN {MODES}),
            ADD COLUMN waitlist_auto_hours integer NOT NULL DEFAULT 3
                CHECK (waitlist_auto_hours BETWEEN 0 AND 72)
    """)
    op.execute(
        "GRANT UPDATE (waitlist_enabled, waitlist_class_mode, waitlist_appointment_mode,"
        " waitlist_resource_mode, waitlist_auto_hours) ON app.tenants TO app_api"
    )
    op.execute(f"""
        ALTER TABLE app.services
            ADD COLUMN waitlist_mode text CHECK (waitlist_mode IN {MODES})
    """)
    _kinds_check((*KINDS_BEFORE, *NEW_KINDS))

    op.execute("""
        CREATE TABLE app.waitlist_requests (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id          uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id          uuid NOT NULL,
            kind               text NOT NULL CHECK (kind IN ('slot', 'range', 'day')),
            service_id         uuid NOT NULL REFERENCES app.services (id) ON DELETE CASCADE,
            staff_user_id      uuid REFERENCES app.users (id) ON DELETE CASCADE,
            location_id        uuid REFERENCES app.locations (id) ON DELETE CASCADE,
            day                date NOT NULL,
            from_time          time,
            to_time            time,
            starts_at          timestamptz,
            status             text NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'offered', 'fulfilled', 'cancelled',
                                                 'expired')),
            offered_session_id uuid REFERENCES app.sessions (id) ON DELETE SET NULL,
            offered_at         timestamptz,
            expires_at         timestamptz NOT NULL,
            created_at         timestamptz NOT NULL DEFAULT now(),
            updated_at         timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            CHECK ((kind = 'range') = (from_time IS NOT NULL AND to_time IS NOT NULL)),
            CHECK (from_time IS NULL OR to_time > from_time),
            CHECK ((kind = 'slot') = (starts_at IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE INDEX waitlist_requests_client ON app.waitlist_requests (tenant_id, client_id)"
        " WHERE status IN ('active', 'offered')"
    )
    op.execute(
        "CREATE INDEX waitlist_requests_match ON app.waitlist_requests"
        " (tenant_id, service_id, day) WHERE status IN ('active', 'offered')"
    )
    op.execute("""
        CREATE TABLE app.waitlist_offers (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id  uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            session_id uuid NOT NULL REFERENCES app.sessions (id) ON DELETE CASCADE,
            client_id  uuid NOT NULL,
            request_id uuid REFERENCES app.waitlist_requests (id) ON DELETE SET NULL,
            booking_id uuid REFERENCES app.bookings (id) ON DELETE SET NULL,
            status     text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'claimed', 'taken')),
            offered_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (session_id, client_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX waitlist_offers_client ON app.waitlist_offers (tenant_id, client_id)")
    # Foreign keys are indexed so deleting a service, branch, class or booking stays cheap.
    for statement in (
        "CREATE INDEX waitlist_requests_service ON app.waitlist_requests (service_id)",
        "CREATE INDEX waitlist_requests_staff ON app.waitlist_requests (staff_user_id)"
        " WHERE staff_user_id IS NOT NULL",
        "CREATE INDEX waitlist_requests_location ON app.waitlist_requests (location_id)"
        " WHERE location_id IS NOT NULL",
        "CREATE INDEX waitlist_requests_offered ON app.waitlist_requests (offered_session_id)"
        " WHERE offered_session_id IS NOT NULL",
        "CREATE INDEX waitlist_offers_request ON app.waitlist_offers (request_id)"
        " WHERE request_id IS NOT NULL",
        "CREATE INDEX waitlist_offers_booking ON app.waitlist_offers (booking_id)"
        " WHERE booking_id IS NOT NULL",
        "CREATE INDEX waitlist_offers_tenant ON app.waitlist_offers (tenant_id)",
    ):
        op.execute(statement)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.waitlist_requests TO app_api")
    op.execute("GRANT SELECT, UPDATE, DELETE ON app.waitlist_offers TO app_api")
    for table in ("waitlist_requests", "waitlist_offers"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)
    # A client sees and manages only their own requests, and reads their own offers.
    op.execute("""
        CREATE POLICY waitlist_requests_client ON app.waitlist_requests TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)
    op.execute("""
        CREATE POLICY waitlist_offers_client ON app.waitlist_offers TO app_api
        USING (client_id = app.current_client_id())
    """)

    op.execute(MODE_FOR)
    op.execute(SLOT_IS_FREE)
    op.execute(MATCHES)
    op.execute(ON_FREED)
    op.execute(ON_BOOKED)
    for signature in (
        "waitlist_mode_for(uuid)",
        "waitlist_slot_is_free(uuid)",
        "waitlist_matches(uuid, uuid)",
        "waitlist_on_freed(uuid)",
        "waitlist_on_booked(uuid, uuid)",
    ):
        _definer_grants(signature)
    op.execute(_promote(gated=True))


def downgrade() -> None:
    # contract: only a rollback of this release drops these; nothing else reads them
    op.execute(_promote(gated=False))
    for signature in (
        "waitlist_on_booked(uuid, uuid)",
        "waitlist_on_freed(uuid)",
        "waitlist_matches(uuid, uuid)",
        "waitlist_slot_is_free(uuid)",
        "waitlist_mode_for(uuid)",
    ):
        op.execute(f"DROP FUNCTION app.{signature}")
    op.execute("DROP TABLE app.waitlist_offers")
    op.execute("DROP TABLE app.waitlist_requests")
    op.execute(
        "DELETE FROM app.notifications WHERE kind IN ('waitlist_spot_open', 'waitlist_spot_taken')"
    )
    _kinds_check(KINDS_BEFORE)
    op.execute("ALTER TABLE app.services DROP COLUMN waitlist_mode")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN waitlist_auto_hours, DROP COLUMN waitlist_resource_mode,
            DROP COLUMN waitlist_appointment_mode, DROP COLUMN waitlist_class_mode,
            DROP COLUMN waitlist_enabled
    """)
