"""Architecture review (#40): tighter database rights and indexes for the hot paths.

- The branch helpers that take a business id (`default_location_id`, `sync_extra_locations_for`)
  are no longer callable by the API role; only the triggers (running as the owner) use them.
  The API keeps its own business's extra-branch charge in step with
  `app.sync_my_extra_locations()`, which reads the business from the request.
- The API may update a business's settings columns, never its id, creation time or trial end
  (the trial changes only through the MyBiz console rule).
- Helper functions are no longer executable by PUBLIC.
- Indexes for queries that ran without one: payments per client and plan, a coach's
  sessions, bookings per session, pending actions, messages, usage across businesses, and
  foreign keys used in joins.

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FILED = ("sessions", "payments", "entitlements", "clients")

TENANT_COLUMNS = (
    "name", "vertical", "locale", "time_zone", "currency", "updated_at", "primary_color", "logo",
    "logo_content_type", "logo_updated_at", "cancellation_window_minutes", "join_code",
    "booking_requires_plan", "requires_health_declaration", "online_sales", "welcome_sent_at",
)  # fmt: skip

INDEXES = (
    ("payments_client_created_idx", "payments", "tenant_id, client_id, created_at"),
    ("payments_entitlement_idx", "payments", "tenant_id, entitlement_id"),
    ("sessions_instructor_starts_idx", "sessions", "tenant_id, instructor_user_id, starts_at"),
    ("sessions_service_idx", "sessions", "tenant_id, service_id"),
    ("bookings_tenant_session_idx", "bookings", "tenant_id, session_id"),
    ("pending_actions_status_idx", "pending_actions", "tenant_id, status, created_at"),
    ("pending_actions_conversation_idx", "pending_actions", "tenant_id, conversation_id"),
    ("messages_created_idx", "messages", "tenant_id, created_at"),
    ("usage_events_occurred_idx", "usage_events", "occurred_at"),
    ("entitlements_plan_idx", "entitlements", "tenant_id, plan_id"),
    ("checkouts_plan_idx", "checkouts", "tenant_id, plan_id"),
    ("session_series_service_idx", "session_series", "tenant_id, service_id"),
    ("lead_activities_lead_idx", "lead_activities", "tenant_id, lead_id"),
    ("client_notes_booking_idx", "client_notes", "booking_id"),
)

HELPERS = ("current_tenant_id()", "current_user_id()", "is_member(uuid)")


def upgrade() -> None:
    # Triggers run the branch helpers as the owner, so the API role needs no rights on them.
    for table in FILED:
        op.execute(f"ALTER FUNCTION app.file_{table}_under_branch() SECURITY DEFINER")
    op.execute("ALTER FUNCTION app.sync_extra_locations() SECURITY DEFINER")
    for function in ("default_location_id(uuid, uuid)", "sync_extra_locations_for(uuid)"):
        op.execute(f"REVOKE EXECUTE ON FUNCTION app.{function} FROM app_api")
    op.execute("""
        CREATE FUNCTION app.sync_my_extra_locations() RETURNS void
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT app.sync_extra_locations_for(app.current_tenant_id())
            WHERE app.current_tenant_id() IS NOT NULL
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.sync_my_extra_locations() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.sync_my_extra_locations() TO app_api")

    op.execute("REVOKE UPDATE ON app.tenants FROM app_api")
    op.execute(f"GRANT UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants TO app_api")

    for function in HELPERS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")
    op.execute("ALTER FUNCTION app.current_user_id() SET search_path = ''")

    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON app.{table} ({columns})")


def downgrade() -> None:
    for name, _, _ in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS app.{name}")
    op.execute("ALTER FUNCTION app.current_user_id() RESET search_path")
    for function in HELPERS:
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO PUBLIC")
    op.execute(f"REVOKE UPDATE ({', '.join(TENANT_COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("GRANT UPDATE ON app.tenants TO app_api")
    op.execute("DROP FUNCTION app.sync_my_extra_locations()")
    for function in ("default_location_id(uuid, uuid)", "sync_extra_locations_for(uuid)"):
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")
    op.execute("ALTER FUNCTION app.sync_extra_locations() SECURITY INVOKER")
    for table in FILED:
        op.execute(f"ALTER FUNCTION app.file_{table}_under_branch() SECURITY INVOKER")
