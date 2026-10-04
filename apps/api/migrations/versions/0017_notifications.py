"""Client notifications: things that happened to a client's bookings and declarations.

The client app shows them as an inbox. Each row stores what to show (kind + a snapshot of
the session) so later changes don't rewrite it; the app renders the text in its language.
Waitlist promotion happens inside app.promote_waitlist (which can run for another client's
cancellation), so the function itself records the promoted client's notification.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
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
)

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
        )
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


def upgrade() -> None:
    kinds = ", ".join(f"'{kind}'" for kind in KINDS)
    op.execute(f"""
        CREATE TABLE app.notifications (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id   uuid NOT NULL,
            kind        text NOT NULL CHECK (kind IN ({kinds})),
            payload     jsonb NOT NULL DEFAULT '{{}}',
            created_at  timestamptz NOT NULL DEFAULT now(),
            read_at     timestamptz,
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX notifications_client_idx "
        "ON app.notifications (tenant_id, client_id, created_at DESC)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.notifications TO app_api")
    op.execute("ALTER TABLE app.notifications ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY notifications_tenant ON app.notifications TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Clients read their own and mark them read; they never create them.
    op.execute("""
        CREATE POLICY notifications_client_select ON app.notifications
        FOR SELECT TO app_api USING (client_id = app.current_client_id())
    """)
    op.execute("""
        CREATE POLICY notifications_client_update ON app.notifications
        FOR UPDATE TO app_api
        USING (client_id = app.current_client_id())
        WITH CHECK (client_id = app.current_client_id())
    """)
    op.execute(PROMOTE)


def downgrade() -> None:
    # The function as migration 0008 created it (no notifications).
    op.execute("""
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
    op.execute("DROP TABLE app.notifications")
