"""On-site jobs (#42, decision X11): appointments at the client's address.

- An appointment service can be on-site (`services.on_site`) with travel time
  (`services.travel_minutes`): the technician is busy from `starts_at - travel` to `ends_at`.
  Free times, staff_busy and the booking check all count it, so jobs never leave too little time
  to get from one to the next.
- Clients have addresses (`app.client_addresses`); clients manage their own in the app.
- A job (an on-site appointment session) keeps the address it was booked for: its id and a
  copy of the text (`sessions.address_id`, `sessions.address`), and a status
  (`sessions.job_status`: scheduled, on_the_way, in_progress, done).

Revision ID: 0047
Revises: 0046
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A session blocks a staff member's time while scheduled and, for appointments, booked; an
# on-site job from its travel time before it.
BUSY = """
    s.status = 'scheduled' AND s.instructor_user_id = {staff}
    AND s.starts_at - make_interval(mins => s.travel_minutes) < {ends} AND s.ends_at > {starts}
    AND (sv.booking_mode = 'class' OR EXISTS (
        SELECT 1 FROM app.bookings b
        WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
    ))
"""
OLD_BUSY = """
    s.status = 'scheduled' AND s.instructor_user_id = {staff}
    AND s.starts_at < {ends} AND s.ends_at > {starts}
    AND (sv.booking_mode = 'class' OR EXISTS (
        SELECT 1 FROM app.bookings b
        WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
    ))
"""
AWAY = """
    EXISTS (
        SELECT 1 FROM app.staff_time_off o
        WHERE o.tenant_id = v_tenant AND o.user_id = p_staff
          AND v_local::date BETWEEN o.starts_on AND o.ends_on
    )
"""


def _staff_busy(busy_sql: str, travel: bool) -> str:
    busy = busy_sql.format(staff="s.instructor_user_id", starts="p_from", ends="p_to")
    starts = "s.starts_at - make_interval(mins => s.travel_minutes)" if travel else "s.starts_at"
    return f"""
        CREATE OR REPLACE FUNCTION app.staff_busy(p_from timestamptz, p_to timestamptz)
        RETURNS TABLE (user_id uuid, starts_at timestamptz, ends_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT s.instructor_user_id, {starts}, s.ends_at
            FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND s.instructor_user_id IS NOT NULL AND {busy}
            UNION ALL
            SELECT o.user_id,
                   (o.starts_on::timestamp AT TIME ZONE t.time_zone),
                   ((o.ends_on + 1)::timestamp AT TIME ZONE t.time_zone)
            FROM app.staff_time_off o JOIN app.tenants t ON t.id = o.tenant_id
            WHERE o.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND (o.starts_on::timestamp AT TIME ZONE t.time_zone) < p_to
              AND ((o.ends_on + 1)::timestamp AT TIME ZONE t.time_zone) > p_from
        $$
    """


CREATE_JOB = f"""
    CREATE FUNCTION app.create_appointment_session(
        p_service uuid, p_staff uuid, p_starts timestamptz, p_address uuid DEFAULT NULL
    ) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
    DECLARE
        v_tenant uuid := coalesce(app.current_tenant_id(), app.client_tenant_id());
        v_service record;
        v_address text;
        v_zone text;
        v_from timestamptz;
        v_ends timestamptz;
        v_local timestamp;
        v_id uuid;
    BEGIN
        IF v_tenant IS NULL THEN
            RAISE EXCEPTION 'no business' USING ERRCODE = '42501';
        END IF;
        SELECT id, duration_minutes, on_site, travel_minutes INTO v_service FROM app.services
        WHERE id = p_service AND tenant_id = v_tenant AND active
          AND booking_mode = 'appointment';
        IF v_service.id IS NULL THEN
            RAISE EXCEPTION 'not an appointment service' USING ERRCODE = 'P0002';
        END IF;
        IF v_service.on_site THEN
            -- A job needs an address of this business's client (a client: one of their own).
            SELECT concat_ws(', ', a.street, nullif(a.details, ''), a.city) INTO v_address
            FROM app.client_addresses a
            WHERE a.id = p_address AND a.tenant_id = v_tenant AND a.active
              AND (app.current_tenant_id() IS NOT NULL OR a.client_id = app.current_client_id());
            IF v_address IS NULL THEN
                RAISE EXCEPTION 'an on-site job needs an address' USING ERRCODE = '22004';
            END IF;
        END IF;
        SELECT time_zone INTO v_zone FROM app.tenants WHERE id = v_tenant;
        v_from := p_starts - make_interval(mins => coalesce(v_service.travel_minutes, 0));
        v_ends := p_starts + make_interval(mins => v_service.duration_minutes);
        v_local := v_from AT TIME ZONE v_zone;
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
        ) OR {AWAY} THEN
            RAISE EXCEPTION 'outside working hours' USING ERRCODE = '22023';
        END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(p_staff::text, 0));
        IF EXISTS (
            SELECT 1 FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = v_tenant
              AND {BUSY.format(staff="p_staff", starts="v_from", ends="v_ends")}
        ) THEN
            RAISE EXCEPTION 'time taken' USING ERRCODE = '23P01';
        END IF;
        INSERT INTO app.sessions
            (tenant_id, service_id, instructor_user_id, capacity, starts_at, ends_at,
             travel_minutes, address_id, address, job_status)
        VALUES (v_tenant, p_service, p_staff, 1, p_starts, v_ends,
                coalesce(v_service.travel_minutes, 0),
                CASE WHEN v_service.on_site THEN p_address END, v_address,
                CASE WHEN v_service.on_site THEN 'scheduled' END)
        RETURNING id INTO v_id;
        RETURN v_id;
    END
    $$
"""

OLD_CREATE = f"""
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
        ) OR {AWAY} THEN
            RAISE EXCEPTION 'outside working hours' USING ERRCODE = '22023';
        END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(p_staff::text, 0));
        IF EXISTS (
            SELECT 1 FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = v_tenant
              AND {OLD_BUSY.format(staff="p_staff", starts="p_starts", ends="v_ends")}
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
"""

GRANTS = """
    REVOKE ALL ON FUNCTION app.create_appointment_session({args}) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.create_appointment_session({args}) TO app_api;
"""


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.services
            ADD COLUMN on_site boolean NOT NULL DEFAULT false,
            ADD COLUMN travel_minutes integer NOT NULL DEFAULT 0
                CHECK (travel_minutes BETWEEN 0 AND 240),
            ADD CONSTRAINT services_on_site_appointment
                CHECK (NOT on_site OR booking_mode = 'appointment')
    """)

    op.execute("""
        CREATE TABLE app.client_addresses (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid NOT NULL,
            label       text CHECK (length(label) <= 40),
            street      text NOT NULL CHECK (length(trim(street)) BETWEEN 1 AND 200),
            city        text NOT NULL CHECK (length(trim(city)) BETWEEN 1 AND 80),
            details     text CHECK (length(details) <= 200),
            notes       text CHECK (length(notes) <= 500),
            active      boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX client_addresses_client ON app.client_addresses (tenant_id, client_id)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.client_addresses TO app_api")
    op.execute("ALTER TABLE app.client_addresses ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY client_addresses_tenant ON app.client_addresses TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY client_addresses_client ON app.client_addresses TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)

    op.execute("""
        ALTER TABLE app.sessions
            ADD COLUMN travel_minutes integer NOT NULL DEFAULT 0
                CHECK (travel_minutes BETWEEN 0 AND 240),
            ADD COLUMN address_id uuid REFERENCES app.client_addresses (id) ON DELETE SET NULL,
            ADD COLUMN address text CHECK (length(address) <= 500),
            ADD COLUMN job_status text
                CHECK (job_status IN ('scheduled', 'on_the_way', 'in_progress', 'done'))
    """)
    op.execute("""
        CREATE INDEX sessions_jobs ON app.sessions (tenant_id, instructor_user_id, starts_at)
        WHERE job_status IS NOT NULL
    """)

    op.execute(_staff_busy(BUSY, travel=True))
    op.execute("DROP FUNCTION app.create_appointment_session(uuid, uuid, timestamptz)")
    op.execute(CREATE_JOB)
    op.execute(GRANTS.format(args="uuid, uuid, timestamptz, uuid"))


def downgrade() -> None:
    op.execute("DROP FUNCTION app.create_appointment_session(uuid, uuid, timestamptz, uuid)")
    op.execute(OLD_CREATE)
    op.execute(GRANTS.format(args="uuid, uuid, timestamptz"))
    op.execute(_staff_busy(OLD_BUSY, travel=False))
    op.execute("DROP INDEX app.sessions_jobs")
    op.execute("""
        ALTER TABLE app.sessions DROP COLUMN job_status, DROP COLUMN address,
            DROP COLUMN address_id, DROP COLUMN travel_minutes
    """)
    op.execute("DROP TABLE app.client_addresses")
    op.execute("""
        ALTER TABLE app.services DROP CONSTRAINT services_on_site_appointment,
            DROP COLUMN travel_minutes, DROP COLUMN on_site
    """)
