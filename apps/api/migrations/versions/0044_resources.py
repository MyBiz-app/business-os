"""Resources (#41, decision X9): courts, rooms and spaces booked by the hour.

A room of a branch can be *bookable*: it then has its own weekly hours (`room_hours`) and serves
resource services (`service_rooms`). A resource service (`booking_mode = 'resource'`) has a
price per hour and lengths a client may choose (minimum, maximum, step). Booking one creates a
one-person *reservation* session in the room, through app.create_resource_session, which checks
the service, the room, the length, the hours and closed days, then that the room is free, and
prices it. Then a normal booking follows, so check-in, reminders, receipts and reports work as
for classes and appointments.

No double booking, even when two people press "book" at the same moment: the function holds an
advisory lock per room, and an exclusion constraint on reservations is the last line.

Revision ID: 0044
Revises: 0043
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Equality on uuid inside a GiST exclusion constraint (a trusted extension, in every Postgres).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # --- Rooms as resources -----------------------------------------------------------------
    op.execute("ALTER TABLE app.rooms ADD COLUMN bookable boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE app.rooms ADD CONSTRAINT rooms_tenant_id_key UNIQUE (tenant_id, id)")
    op.execute("""
        CREATE TABLE app.room_hours (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            room_id     uuid NOT NULL,
            weekday     smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
            starts      time NOT NULL,
            ends        time NOT NULL CHECK (ends > starts),
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, room_id) REFERENCES app.rooms (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX room_hours_room ON app.room_hours (tenant_id, room_id, weekday)")

    # --- Resource services --------------------------------------------------------------------
    op.execute("ALTER TABLE app.services DROP CONSTRAINT services_booking_mode_check")
    op.execute("""
        ALTER TABLE app.services ADD CONSTRAINT services_booking_mode_check
            CHECK (booking_mode IN ('class', 'appointment', 'resource'))
    """)
    op.execute("""
        ALTER TABLE app.services
            ADD COLUMN min_minutes     integer CHECK (min_minutes BETWEEN 15 AND 1440),
            ADD COLUMN max_minutes     integer CHECK (max_minutes BETWEEN 15 AND 1440),
            ADD COLUMN step_minutes    integer CHECK (step_minutes BETWEEN 15 AND 240),
            ADD COLUMN price_per_hour  integer CHECK (price_per_hour >= 0),
            ADD CONSTRAINT services_resource_lengths CHECK (
                booking_mode <> 'resource' OR (
                    min_minutes IS NOT NULL AND max_minutes IS NOT NULL
                    AND step_minutes IS NOT NULL AND price_per_hour IS NOT NULL
                    AND max_minutes >= min_minutes
                    AND (max_minutes - min_minutes) % step_minutes = 0
                )
            )
    """)
    op.execute("""
        CREATE TABLE app.service_rooms (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            service_id  uuid NOT NULL,
            room_id     uuid NOT NULL,
            PRIMARY KEY (service_id, room_id),
            FOREIGN KEY (tenant_id, service_id) REFERENCES app.services (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, room_id) REFERENCES app.rooms (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX service_rooms_room ON app.service_rooms (tenant_id, room_id)")

    for table in ("room_hours", "service_rooms"):
        op.execute(f"GRANT SELECT, INSERT, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)
        # Clients see when and where they can book (free times come from the hours).
        op.execute(f"""
            CREATE POLICY {table}_client_select ON app.{table} FOR SELECT TO app_api
            USING (tenant_id = app.client_tenant_id())
        """)

    # --- Reservations ---------------------------------------------------------------------------
    # A reservation is a session that holds a room; its price is fixed when it is made.
    op.execute("""
        ALTER TABLE app.sessions
            ADD COLUMN reserved boolean NOT NULL DEFAULT false,
            ADD COLUMN price_amount integer CHECK (price_amount >= 0),
            ADD COLUMN price_currency text CHECK (price_currency ~ '^[A-Z]{3}$'),
            ADD CONSTRAINT sessions_reservation_room CHECK (NOT reserved OR room_id IS NOT NULL)
    """)
    op.execute("""
        ALTER TABLE app.sessions ADD CONSTRAINT sessions_no_double_reservation
            EXCLUDE USING gist (
                room_id WITH =, tstzrange(starts_at, ends_at) WITH &&
            ) WHERE (reserved AND status = 'scheduled')
    """)

    op.execute("""
        CREATE FUNCTION app.create_resource_session(
            p_service uuid, p_room uuid, p_starts timestamptz, p_minutes integer
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid := coalesce(app.current_tenant_id(), app.client_tenant_id());
            v_service record;
            v_room record;
            v_zone text;
            v_ends timestamptz;
            v_local timestamp;
            v_id uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no business' USING ERRCODE = '42501';
            END IF;
            SELECT id, min_minutes, max_minutes, step_minutes, price_per_hour, price_currency
            INTO v_service FROM app.services
            WHERE id = p_service AND tenant_id = v_tenant AND active
              AND booking_mode = 'resource';
            SELECT r.id, r.location_id INTO v_room FROM app.rooms r
            JOIN app.service_rooms sr ON sr.room_id = r.id AND sr.service_id = p_service
            JOIN app.locations l ON l.id = r.location_id AND l.active
            WHERE r.id = p_room AND r.tenant_id = v_tenant AND r.active AND r.bookable;
            IF v_service.id IS NULL OR v_room.id IS NULL THEN
                RAISE EXCEPTION 'not a resource of this service' USING ERRCODE = 'P0002';
            END IF;
            IF p_minutes < v_service.min_minutes OR p_minutes > v_service.max_minutes
               OR (p_minutes - v_service.min_minutes) % v_service.step_minutes <> 0 THEN
                RAISE EXCEPTION 'length not offered' USING ERRCODE = '22003';
            END IF;
            SELECT time_zone INTO v_zone FROM app.tenants WHERE id = v_tenant;
            v_ends := p_starts + make_interval(mins => p_minutes);
            v_local := p_starts AT TIME ZONE v_zone;
            -- Inside one of the room's opening-hour blocks, on a day the business is open.
            IF NOT EXISTS (
                SELECT 1 FROM app.room_hours h
                WHERE h.tenant_id = v_tenant AND h.room_id = p_room
                  AND h.weekday = extract(isodow FROM v_local)::int - 1
                  AND h.starts <= v_local::time
                  AND h.ends >= (v_ends AT TIME ZONE v_zone)::time
                  AND (v_ends AT TIME ZONE v_zone)::date = v_local::date
            ) OR EXISTS (
                SELECT 1 FROM app.closed_days d
                WHERE d.tenant_id = v_tenant AND d.day = v_local::date
            ) THEN
                RAISE EXCEPTION 'outside opening hours' USING ERRCODE = '22023';
            END IF;
            -- One booking at a time per room; any scheduled session there (a class too) blocks it.
            PERFORM pg_advisory_xact_lock(hashtextextended(p_room::text, 0));
            IF EXISTS (
                SELECT 1 FROM app.sessions s
                WHERE s.tenant_id = v_tenant AND s.room_id = p_room AND s.status = 'scheduled'
                  AND s.starts_at < v_ends AND s.ends_at > p_starts
            ) THEN
                RAISE EXCEPTION 'time taken' USING ERRCODE = '23P01';
            END IF;
            INSERT INTO app.sessions
                (tenant_id, service_id, location_id, room_id, capacity, starts_at, ends_at,
                 reserved, price_amount, price_currency)
            VALUES (v_tenant, p_service, v_room.location_id, p_room, 1, p_starts, v_ends, true,
                    round(v_service.price_per_hour * p_minutes / 60.0)::integer,
                    v_service.price_currency)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    signature = "app.create_resource_session(uuid, uuid, timestamptz, integer)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")

    # A cancelled reservation frees the room: its session is cancelled with its booking
    # (whoever cancels it, the client in the app or the front desk).
    op.execute("""
        CREATE FUNCTION app.release_reservation() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            UPDATE app.sessions s SET status = 'cancelled', updated_at = now()
            WHERE s.id = NEW.session_id AND s.reserved AND s.status = 'scheduled'
              AND NOT EXISTS (
                  SELECT 1 FROM app.bookings b
                  WHERE b.session_id = s.id AND b.status <> 'cancelled'
              );
            RETURN NULL;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.release_reservation() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER bookings_release_reservation
        AFTER UPDATE OF status ON app.bookings
        FOR EACH ROW WHEN (NEW.status = 'cancelled' AND OLD.status <> 'cancelled')
        EXECUTE FUNCTION app.release_reservation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER bookings_release_reservation ON app.bookings")
    op.execute("DROP FUNCTION app.release_reservation()")
    op.execute("DROP FUNCTION app.create_resource_session(uuid, uuid, timestamptz, integer)")
    op.execute("DELETE FROM app.sessions WHERE reserved")
    op.execute("ALTER TABLE app.sessions DROP CONSTRAINT sessions_no_double_reservation")
    op.execute("""
        ALTER TABLE app.sessions
            DROP CONSTRAINT sessions_reservation_room,
            DROP COLUMN price_currency, DROP COLUMN price_amount, DROP COLUMN reserved
    """)
    op.execute("DROP TABLE app.service_rooms")
    op.execute("DELETE FROM app.services WHERE booking_mode = 'resource'")
    op.execute("""
        ALTER TABLE app.services
            DROP CONSTRAINT services_resource_lengths,
            DROP COLUMN price_per_hour, DROP COLUMN step_minutes,
            DROP COLUMN max_minutes, DROP COLUMN min_minutes
    """)
    op.execute("ALTER TABLE app.services DROP CONSTRAINT services_booking_mode_check")
    op.execute("""
        ALTER TABLE app.services ADD CONSTRAINT services_booking_mode_check
            CHECK (booking_mode IN ('class', 'appointment'))
    """)
    op.execute("DROP TABLE app.room_hours")
    op.execute("ALTER TABLE app.rooms DROP CONSTRAINT rooms_tenant_id_key")
    op.execute("ALTER TABLE app.rooms DROP COLUMN bookable")
