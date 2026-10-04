"""Appointments: services booked one-to-one with a staff member at a free time (barbers, clinics,
garages), next to the existing group classes.

A service's booking_mode says how it is booked. Staff publish weekly working hours; free times
come from those hours minus the staff member's other sessions. Booking an appointment creates a
one-person session for that time and books it, so reports, reminders and check-in work as for
classes. Clients cannot insert sessions, so the session is created by
app.create_appointment_session, which checks the service, the hours and that the time is free.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A session blocks a staff member's time while it is scheduled and, for appointments, booked.
BUSY = """
    s.status = 'scheduled' AND s.instructor_user_id = {staff}
    AND s.starts_at < {ends} AND s.ends_at > {starts}
    AND (sv.booking_mode = 'class' OR EXISTS (
        SELECT 1 FROM app.bookings b
        WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
    ))
"""


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.services ADD COLUMN booking_mode text NOT NULL DEFAULT 'class'
            CHECK (booking_mode IN ('class', 'appointment'))
    """)

    op.execute("""
        CREATE TABLE app.staff_hours (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL,
            weekday     smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
            starts      time NOT NULL,
            ends        time NOT NULL CHECK (ends > starts),
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX staff_hours_user ON app.staff_hours (tenant_id, user_id, weekday)")
    op.execute("GRANT SELECT, INSERT, DELETE ON app.staff_hours TO app_api")
    op.execute("ALTER TABLE app.staff_hours ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY staff_hours_tenant ON app.staff_hours TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Clients see when they can book (free times are computed from the hours).
    op.execute("""
        CREATE POLICY staff_hours_client_select ON app.staff_hours FOR SELECT TO app_api
        USING (tenant_id = app.client_tenant_id())
    """)

    # Who takes appointments, with a display name; for staff and for the business's clients.
    op.execute("""
        CREATE FUNCTION app.appointment_staff()
        RETURNS TABLE (user_id uuid, name text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT DISTINCT m.user_id,
                   coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1))
            FROM app.tenant_members m
            JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND EXISTS (SELECT 1 FROM app.staff_hours h
                          WHERE h.tenant_id = m.tenant_id AND h.user_id = m.user_id)
            ORDER BY 2
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.appointment_staff() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.appointment_staff() TO app_api")

    # Busy intervals only (no names): clients see other clients' bookings only as busy time.
    busy_any = BUSY.format(staff="s.instructor_user_id", starts="p_from", ends="p_to")
    op.execute(f"""
        CREATE FUNCTION app.staff_busy(p_from timestamptz, p_to timestamptz)
        RETURNS TABLE (user_id uuid, starts_at timestamptz, ends_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT s.instructor_user_id, s.starts_at, s.ends_at
            FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND s.instructor_user_id IS NOT NULL AND {busy_any}
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.staff_busy(timestamptz, timestamptz) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.staff_busy(timestamptz, timestamptz) TO app_api")

    busy = BUSY.format(staff="p_staff", starts="p_starts", ends="v_ends")
    op.execute(f"""
        CREATE FUNCTION app.create_appointment_session(
            p_service uuid, p_staff uuid, p_starts timestamptz
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid := coalesce(app.current_tenant_id(), app.client_tenant_id());
            v_service record;
            v_zone text;
            v_ends timestamptz;
            v_local timestamp;
            v_id uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no business' USING ERRCODE = '42501';
            END IF;
            SELECT id, duration_minutes INTO v_service FROM app.services
            WHERE id = p_service AND tenant_id = v_tenant AND active
              AND booking_mode = 'appointment';
            IF v_service.id IS NULL THEN
                RAISE EXCEPTION 'not an appointment service' USING ERRCODE = 'P0002';
            END IF;
            SELECT time_zone INTO v_zone FROM app.tenants WHERE id = v_tenant;
            v_ends := p_starts + make_interval(mins => v_service.duration_minutes);
            v_local := p_starts AT TIME ZONE v_zone;
            -- Inside one of the staff member's working-hour blocks, on a day the business is open.
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
            ) THEN
                RAISE EXCEPTION 'outside working hours' USING ERRCODE = '22023';
            END IF;
            -- One booking at a time per staff member.
            PERFORM pg_advisory_xact_lock(hashtextextended(p_staff::text, 0));
            IF EXISTS (
                SELECT 1 FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
                WHERE s.tenant_id = v_tenant AND {busy}
            ) THEN
                RAISE EXCEPTION 'time taken' USING ERRCODE = '23P01';
            END IF;
            INSERT INTO app.sessions
                (tenant_id, service_id, instructor_user_id, capacity, starts_at, ends_at)
            VALUES (v_tenant, p_service, p_staff, 1, p_starts, v_ends)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    signature = "app.create_appointment_session(uuid, uuid, timestamptz)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.create_appointment_session(uuid, uuid, timestamptz)")
    op.execute("DROP FUNCTION app.staff_busy(timestamptz, timestamptz)")
    op.execute("DROP FUNCTION app.appointment_staff()")
    op.execute("DROP TABLE app.staff_hours")
    op.execute("ALTER TABLE app.services DROP COLUMN booking_mode")
