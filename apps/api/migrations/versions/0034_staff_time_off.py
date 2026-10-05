"""Staff time off (vacation, sick days): whole local days when a staff member takes no
appointments. Time off counts as busy time, so no free times are offered, and booking an
appointment in it is refused like a time outside working hours.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same as migration 0027: a session blocks a staff member's time while scheduled and, for
# appointments, booked.
BUSY = """
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


def _create_appointment_session(extra_check: str) -> str:
    busy = BUSY.format(staff="p_staff", starts="p_starts", ends="v_ends")
    return f"""
        CREATE OR REPLACE FUNCTION app.create_appointment_session(
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
            ){extra_check} THEN
                RAISE EXCEPTION 'outside working hours' USING ERRCODE = '22023';
            END IF;
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
    """


def _staff_busy(with_time_off: bool) -> str:
    busy = BUSY.format(staff="s.instructor_user_id", starts="p_from", ends="p_to")
    time_off = """
            UNION ALL
            SELECT o.user_id,
                   (o.starts_on::timestamp AT TIME ZONE t.time_zone),
                   ((o.ends_on + 1)::timestamp AT TIME ZONE t.time_zone)
            FROM app.staff_time_off o JOIN app.tenants t ON t.id = o.tenant_id
            WHERE o.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND (o.starts_on::timestamp AT TIME ZONE t.time_zone) < p_to
              AND ((o.ends_on + 1)::timestamp AT TIME ZONE t.time_zone) > p_from
    """
    return f"""
        CREATE OR REPLACE FUNCTION app.staff_busy(p_from timestamptz, p_to timestamptz)
        RETURNS TABLE (user_id uuid, starts_at timestamptz, ends_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT s.instructor_user_id, s.starts_at, s.ends_at
            FROM app.sessions s JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
              AND s.instructor_user_id IS NOT NULL AND {busy}
            {time_off if with_time_off else ""}
        $$
    """


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.staff_time_off (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL,
            starts_on   date NOT NULL,
            ends_on     date NOT NULL CHECK (ends_on >= starts_on),
            reason      text CHECK (length(reason) <= 200),
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX staff_time_off_user ON app.staff_time_off (tenant_id, user_id)")
    op.execute("GRANT SELECT, INSERT, DELETE ON app.staff_time_off TO app_api")
    op.execute("ALTER TABLE app.staff_time_off ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY staff_time_off_tenant ON app.staff_time_off TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute(_staff_busy(with_time_off=True))
    op.execute(_create_appointment_session(f" OR {AWAY}"))


def downgrade() -> None:
    op.execute(_create_appointment_session(""))
    op.execute(_staff_busy(with_time_off=False))
    op.execute("DROP TABLE app.staff_time_off")
