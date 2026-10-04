"""Client access: end customers sign in and use the business's client app.

A client is linked to a signed-in user through `clients.user_id`. A client request selects
the business the same way staff requests do (`app.tenant_id`), but `app.current_tenant_id()`
stays NULL for non-members, so none of the staff policies apply. Instead, narrow client
policies expose the business's public catalog and schedule, and only the client's own row
and bookings.

Capacity and the waitlist involve other clients' bookings, which a client must never read,
so the counting, locking and promotion run in SECURITY DEFINER functions that staff and
client requests share.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.clients
        ADD COLUMN user_id uuid REFERENCES app.users (id) ON DELETE SET NULL
    """)
    op.execute(
        "CREATE UNIQUE INDEX clients_tenant_user_key ON app.clients (tenant_id, user_id) "
        "WHERE user_id IS NOT NULL"
    )
    op.execute("CREATE INDEX clients_user_idx ON app.clients (user_id)")

    # Short, human-friendly code that clients type or scan to join a business.
    # Alphabet without look-alikes (no 0/O, 1/I/L).
    op.execute("""
        CREATE FUNCTION app.new_join_code() RETURNS text
        LANGUAGE sql VOLATILE SET search_path = ''
        AS $$
            SELECT string_agg(
                substr('ABCDEFGHJKMNPQRSTUVWXYZ23456789', 1 + floor(random() * 31)::int, 1), '')
            FROM generate_series(1, 8)
        $$
    """)
    op.execute("ALTER TABLE app.tenants ADD COLUMN join_code text")
    op.execute("UPDATE app.tenants SET join_code = app.new_join_code()")
    op.execute("""
        ALTER TABLE app.tenants
            ALTER COLUMN join_code SET DEFAULT app.new_join_code(),
            ALTER COLUMN join_code SET NOT NULL,
            ADD CONSTRAINT tenants_join_code_key UNIQUE (join_code)
    """)

    op.execute("""
        CREATE FUNCTION app.current_client_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT c.id FROM app.clients c
            WHERE c.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND c.user_id = app.current_user_id()
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.client_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT c.tenant_id FROM app.clients c
            WHERE c.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND c.user_id = app.current_user_id()
        $$
    """)
    # The business a staff member or client is currently acting in.
    op.execute("""
        CREATE FUNCTION app.acting_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SET search_path = ''
        AS $$ SELECT coalesce(app.current_tenant_id(), app.client_tenant_id()) $$
    """)

    # Read-only access for clients to what a business shows its customers.
    op.execute("""
        CREATE POLICY tenants_client_select ON app.tenants FOR SELECT TO app_api
        USING (EXISTS (
            SELECT 1 FROM app.clients c
            WHERE c.tenant_id = app.tenants.id AND c.user_id = app.current_user_id()
        ))
    """)
    for table in ("services", "locations", "rooms", "sessions"):
        op.execute(f"""
            CREATE POLICY {table}_client_select ON app.{table} FOR SELECT TO app_api
            USING (tenant_id = app.client_tenant_id())
        """)
    # A signed-in user sees their own client records in every business they joined.
    op.execute("""
        CREATE POLICY clients_own_select ON app.clients FOR SELECT TO app_api
        USING (user_id = app.current_user_id())
    """)
    op.execute("""
        CREATE POLICY bookings_client ON app.bookings TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id() AND tenant_id = app.client_tenant_id())
    """)

    # Occupancy of a session, for staff and clients alike.
    op.execute("""
        CREATE FUNCTION app.session_counts(p_session_id uuid)
        RETURNS TABLE (booked integer, waitlisted integer)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT count(*) FILTER (WHERE b.status IN ('booked', 'checked_in', 'no_show'))::int,
                   count(*) FILTER (WHERE b.status = 'waitlisted')::int
            FROM app.bookings b
            WHERE b.session_id = p_session_id AND b.tenant_id = app.acting_tenant_id()
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.lock_session(p_session_id uuid)
        RETURNS TABLE (capacity integer, status text, starts_at timestamptz)
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT s.capacity, s.status, s.starts_at FROM app.sessions s
            WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id()
            FOR UPDATE
        $$
    """)
    # 1-based place on the waitlist, counting other clients' bookings too.
    op.execute("""
        CREATE FUNCTION app.waitlist_position(p_booking_id uuid) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT count(*)::int FROM app.bookings b
            JOIN app.bookings w ON w.session_id = b.session_id AND w.status = 'waitlisted'
                AND (w.waitlisted_at, w.id) <= (b.waitlisted_at, b.id)
            WHERE b.id = p_booking_id AND b.status = 'waitlisted'
              AND b.tenant_id = app.acting_tenant_id()
            HAVING count(*) > 0
        $$
    """)
    # Moves the earliest waitlisted clients into free spots of an upcoming session.
    # Callers hold the session lock (app.lock_session) in the same transaction.
    op.execute("""
        CREATE FUNCTION app.promote_waitlist(p_session_id uuid) RETURNS integer
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_free integer;
            v_promoted integer;
        BEGIN
            SELECT s.capacity - (
                SELECT count(*) FROM app.bookings b
                WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
            )
            INTO v_free
            FROM app.sessions s
            WHERE s.id = p_session_id AND s.tenant_id = app.acting_tenant_id()
              AND s.status = 'scheduled' AND s.starts_at > now();
            IF coalesce(v_free, 0) <= 0 THEN
                RETURN 0;
            END IF;
            UPDATE app.bookings SET status = 'booked', updated_at = now()
            WHERE id IN (
                SELECT b.id FROM app.bookings b
                WHERE b.session_id = p_session_id AND b.status = 'waitlisted'
                ORDER BY b.waitlisted_at, b.id
                LIMIT v_free
            );
            GET DIAGNOSTICS v_promoted = ROW_COUNT;
            RETURN v_promoted;
        END
        $$
    """)

    # Before signing in, a client sees only the business's name and branding.
    op.execute("""
        CREATE FUNCTION app.business_by_join_code(p_code text)
        RETURNS TABLE (id uuid, name text, locale text, primary_color text,
                       logo_updated_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id, t.name, t.locale, t.primary_color,
                   CASE WHEN t.logo IS NULL THEN NULL ELSE t.logo_updated_at END
            FROM app.tenants t WHERE t.join_code = upper(trim(p_code))
        $$
    """)
    # Joining links the signed-in user to a client record: an existing record with the same
    # (verified) email is claimed, otherwise a new one is created.
    op.execute("""
        CREATE FUNCTION app.join_business(p_code text) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user app.users%ROWTYPE;
            v_tenant_id uuid;
            v_client_id uuid;
        BEGIN
            SELECT * INTO v_user FROM app.users WHERE id = app.current_user_id();
            IF v_user.id IS NULL THEN
                RAISE EXCEPTION 'no current user' USING ERRCODE = '42501';
            END IF;
            SELECT t.id INTO v_tenant_id FROM app.tenants t
            WHERE t.join_code = upper(trim(p_code));
            IF v_tenant_id IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT c.id INTO v_client_id FROM app.clients c
            WHERE c.tenant_id = v_tenant_id AND c.user_id = v_user.id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            UPDATE app.clients c SET user_id = v_user.id, updated_at = now()
            WHERE c.id = (
                SELECT c2.id FROM app.clients c2
                WHERE c2.tenant_id = v_tenant_id AND c2.user_id IS NULL
                  AND lower(c2.email) = lower(v_user.email)
                LIMIT 1
            )
            RETURNING c.id INTO v_client_id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            INSERT INTO app.clients (tenant_id, user_id, first_name, email, status)
            VALUES (v_tenant_id, v_user.id,
                    coalesce(nullif(trim(v_user.full_name), ''), split_part(v_user.email, '@', 1)),
                    v_user.email, 'active')
            RETURNING id INTO v_client_id;
            RETURN v_client_id;
        END
        $$
    """)

    functions = (
        "new_join_code()",
        "current_client_id()",
        "client_tenant_id()",
        "acting_tenant_id()",
        "session_counts(uuid)",
        "waitlist_position(uuid)",
        "lock_session(uuid)",
        "promote_waitlist(uuid)",
        "business_by_join_code(text)",
        "join_business(text)",
    )
    for function in functions:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in (
        "join_business(text)",
        "business_by_join_code(text)",
        "promote_waitlist(uuid)",
        "lock_session(uuid)",
        "waitlist_position(uuid)",
        "session_counts(uuid)",
    ):
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP POLICY bookings_client ON app.bookings")
    op.execute("DROP POLICY clients_own_select ON app.clients")
    for table in ("services", "locations", "rooms", "sessions"):
        op.execute(f"DROP POLICY {table}_client_select ON app.{table}")
    op.execute("DROP POLICY tenants_client_select ON app.tenants")
    op.execute("DROP FUNCTION app.acting_tenant_id()")
    op.execute("DROP FUNCTION app.client_tenant_id()")
    op.execute("DROP FUNCTION app.current_client_id()")
    op.execute("ALTER TABLE app.tenants DROP COLUMN join_code")
    op.execute("DROP FUNCTION app.new_join_code()")
    op.execute("DROP INDEX app.clients_user_idx")
    op.execute("DROP INDEX app.clients_tenant_user_key")
    op.execute("ALTER TABLE app.clients DROP COLUMN user_id")
