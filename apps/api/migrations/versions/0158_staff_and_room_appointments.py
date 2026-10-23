"""A private lesson takes a staff member and a room together (slice C4, model M5).

A tennis lesson on a court, a treatment in a treatment room: the service says it needs a room
(`services.needs_resource`) and which rooms can serve it (the existing `service_rooms`). The
function `app.create_staff_resource_session` books both at once: the staff member must be free
and inside their hours, a linked room must be open and free, and the session holds the room
(`sessions.holds_room`). A cancelled booking frees the room, like a reservation does.

The room is held by an exclusion constraint on top of the per-room lock, so two people pressing
"book" together never get the same court. A trigger refuses an appointment session of a service
that needs a room when it holds none, so no path can skip the room.

Nothing changes for existing services: the flag defaults to off.

Revision ID: 0158
Revises: 0157
Create Date: 2026-10-23
"""

# contract: only the downgrade drops what this migration added; the upgrade just adds columns,
# a constraint, a trigger and a function and replaces one trigger function.

from collections.abc import Sequence

from alembic import op

revision: str = "0158"
down_revision: str | None = "0157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = "app.create_staff_resource_session(uuid, uuid, uuid, timestamptz)"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.services
            ADD COLUMN needs_resource boolean NOT NULL DEFAULT false,
            ADD CONSTRAINT services_needs_resource_appointment
                CHECK (NOT needs_resource OR (booking_mode = 'appointment' AND NOT on_site))
    """)
    op.execute("""
        ALTER TABLE app.sessions
            ADD COLUMN holds_room boolean NOT NULL DEFAULT false,
            ADD CONSTRAINT sessions_holds_room_has_room
                CHECK (NOT holds_room OR room_id IS NOT NULL),
            ADD CONSTRAINT sessions_no_double_hold
                EXCLUDE USING gist (
                    room_id WITH =, tstzrange(starts_at, ends_at) WITH &&
                ) WHERE (holds_room AND status = 'scheduled')
    """)

    op.execute("""
        CREATE FUNCTION app.create_staff_resource_session(
            p_service uuid, p_staff uuid, p_room uuid, p_starts timestamptz
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid := coalesce(app.current_tenant_id(), app.client_tenant_id());
            v_service record;
            v_room record;
            v_zone text;
            v_ends timestamptz;
            v_local timestamp;
            v_open boolean := false;
            v_id uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no business' USING ERRCODE = '42501';
            END IF;
            SELECT id, duration_minutes INTO v_service FROM app.services
            WHERE id = p_service AND tenant_id = v_tenant AND active
              AND booking_mode = 'appointment' AND needs_resource;
            IF v_service.id IS NULL THEN
                RAISE EXCEPTION 'not a staff and room service' USING ERRCODE = 'P0002';
            END IF;
            SELECT time_zone INTO v_zone FROM app.tenants WHERE id = v_tenant;
            v_ends := p_starts + make_interval(mins => v_service.duration_minutes);
            v_local := p_starts AT TIME ZONE v_zone;
            -- The staff member: inside a working-hour block, on a day the business is open,
            -- and not away.
            IF NOT EXISTS (
                SELECT 1 FROM app.staff_hours h
                WHERE h.tenant_id = v_tenant AND h.user_id = p_staff
                  AND h.weekday = extract(isodow FROM v_local)::int - 1
                  AND h.starts <= v_local::time
                  AND h.ends >= (v_ends AT TIME ZONE v_zone)::time
                  AND (v_ends AT TIME ZONE v_zone)::date = v_local::date
            ) OR EXISTS (
                SELECT 1 FROM app.closed_days d
                WHERE d.tenant_id = v_tenant AND d.day = v_local::date
            ) OR EXISTS (
                SELECT 1 FROM app.staff_time_off o
                WHERE o.tenant_id = v_tenant AND o.user_id = p_staff
                  AND v_local::date BETWEEN o.starts_on AND o.ends_on
            ) THEN
                RAISE EXCEPTION 'outside working hours' USING ERRCODE = '22023';
            END IF;
            -- Locks are taken in a fixed order (the staff member, then rooms by name), so two
            -- bookings at once cannot wait on each other.
            PERFORM pg_advisory_xact_lock(hashtextextended(p_staff::text, 0));
            IF EXISTS (
                SELECT 1 FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
                WHERE s.tenant_id = v_tenant AND s.status = 'scheduled'
                  AND s.instructor_user_id = p_staff
                  AND s.starts_at - make_interval(mins => s.travel_minutes) < v_ends
                  AND s.ends_at > p_starts
                  AND (sv.booking_mode = 'class' OR EXISTS (
                      SELECT 1 FROM app.bookings b
                      WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
                  ))
            ) THEN
                RAISE EXCEPTION 'time taken' USING ERRCODE = '23P01';
            END IF;
            -- The room: the one asked for, or the first free one that serves the service.
            FOR v_room IN
                SELECT r.id, r.location_id FROM app.service_rooms sr
                JOIN app.rooms r ON r.id = sr.room_id AND r.active AND r.bookable
                JOIN app.locations l ON l.id = r.location_id AND l.active
                WHERE sr.service_id = p_service AND sr.tenant_id = v_tenant
                  AND (p_room IS NULL OR r.id = p_room)
                ORDER BY l.name, r.name, r.id
            LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM app.room_hours h
                    WHERE h.tenant_id = v_tenant AND h.room_id = v_room.id
                      AND h.weekday = extract(isodow FROM v_local)::int - 1
                      AND h.starts <= v_local::time
                      AND h.ends >= (v_ends AT TIME ZONE v_zone)::time
                      AND (v_ends AT TIME ZONE v_zone)::date = v_local::date
                ) THEN
                    CONTINUE;
                END IF;
                v_open := true;
                PERFORM pg_advisory_xact_lock(hashtextextended(v_room.id::text, 0));
                IF EXISTS (
                    SELECT 1 FROM app.sessions s
                    WHERE s.tenant_id = v_tenant AND s.room_id = v_room.id
                      AND s.status = 'scheduled' AND s.starts_at < v_ends AND s.ends_at > p_starts
                ) THEN
                    CONTINUE;
                END IF;
                INSERT INTO app.sessions
                    (tenant_id, service_id, location_id, room_id, instructor_user_id, capacity,
                     starts_at, ends_at, holds_room)
                VALUES (v_tenant, p_service, v_room.location_id, v_room.id, p_staff, 1,
                        p_starts, v_ends, true)
                RETURNING id INTO v_id;
                RETURN v_id;
            END LOOP;
            IF p_room IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM app.service_rooms sr
                JOIN app.rooms r ON r.id = sr.room_id AND r.active AND r.bookable
                JOIN app.locations l ON l.id = r.location_id AND l.active
                WHERE sr.service_id = p_service AND sr.tenant_id = v_tenant AND r.id = p_room
            ) THEN
                RAISE EXCEPTION 'not a room of this service' USING ERRCODE = 'P0002';
            END IF;
            IF NOT v_open THEN
                RAISE EXCEPTION 'outside opening hours' USING ERRCODE = '22023';
            END IF;
            RAISE EXCEPTION 'time taken' USING ERRCODE = '23P01';
        END
        $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO app_api")

    # A service that needs a room never gets an appointment without one, by whatever path.
    op.execute("""
        CREATE FUNCTION app.require_room_for_service() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT NEW.holds_room AND EXISTS (
                SELECT 1 FROM app.services sv WHERE sv.id = NEW.service_id AND sv.needs_resource
            ) THEN
                RAISE EXCEPTION 'this service needs a room' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.require_room_for_service() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER sessions_require_room
        BEFORE INSERT ON app.sessions
        FOR EACH ROW EXECUTE FUNCTION app.require_room_for_service()
    """)

    # A cancelled booking frees the room it held, as a cancelled reservation does.
    op.execute("""
        CREATE OR REPLACE FUNCTION app.release_reservation() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            UPDATE app.sessions s SET status = 'cancelled', updated_at = now()
            WHERE s.id = NEW.session_id AND (s.reserved OR s.holds_room)
              AND s.status = 'scheduled'
              AND NOT EXISTS (
                  SELECT 1 FROM app.bookings b
                  WHERE b.session_id = s.id AND b.status <> 'cancelled'
              );
            RETURN NULL;
        END
        $$
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION app.release_reservation() RETURNS trigger
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
    op.execute("DROP TRIGGER sessions_require_room ON app.sessions")
    op.execute("DROP FUNCTION app.require_room_for_service()")
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    op.execute("DELETE FROM app.sessions WHERE holds_room")
    op.execute("""
        ALTER TABLE app.sessions
            DROP CONSTRAINT sessions_no_double_hold,
            DROP CONSTRAINT sessions_holds_room_has_room,
            DROP COLUMN holds_room
    """)
    op.execute("""
        ALTER TABLE app.services
            DROP CONSTRAINT services_needs_resource_appointment,
            DROP COLUMN needs_resource
    """)
