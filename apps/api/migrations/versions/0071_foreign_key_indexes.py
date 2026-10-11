"""Indexes behind the foreign keys that had none (review item P1-4).

Supabase's advisor listed 55 foreign keys on staging without a covering index. Postgres checks
every one of them when the parent row is deleted or its key changes, so removing a client, a
branch, a room or a plan read the whole child table. These indexes cover the keys that point at
business data: clients, leads, branches, rooms, stations, series, plans, quotes, entitlements
and the team. Five tables (client notes, contact requests, entitlement freezes, message
templates, quote lines) also had no index starting with `tenant_id`, which every RLS policy
filters on.

Left out on purpose: the "who did it" keys to `app.users` (`created_by`, `sold_by`,
`reviewed_by`...). Nothing filters on them and a person is almost never deleted, so an index
would only slow down every insert.

Two older indexes are replaced by wider ones with the same leading columns, so every query that
used them can use the new one: `bookings_client_idx` and `sessions_location`.

Revision ID: 0071
Revises: 0070
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table, columns). Each index covers the foreign key with the same columns.
INDEXES: list[tuple[str, str, str]] = [
    ("bookings_client_dependent", "bookings", "tenant_id, client_id, dependent_id"),
    ("bookings_tenant_entitlement", "bookings", "tenant_id, entitlement_id"),
    ("checkouts_entitlement", "checkouts", "tenant_id, entitlement_id"),
    ("checkouts_promo_code", "checkouts", "tenant_id, promo_code_id"),
    ("checkouts_quote", "checkouts", "quote_id"),
    ("client_notes_tenant_client", "client_notes", "tenant_id, client_id, created_at"),
    ("contact_requests_tenant", "contact_requests", "tenant_id"),
    ("entitlement_freezes_entitlement", "entitlement_freezes", "tenant_id, entitlement_id"),
    ("leads_tenant_client", "leads", "tenant_id, client_id"),
    ("leads_owner", "leads", "tenant_id, owner_user_id"),
    ("message_templates_tenant", "message_templates", "tenant_id, name"),
    ("messages_tenant_client", "messages", "tenant_id, client_id, created_at"),
    ("messages_tenant_lead", "messages", "tenant_id, lead_id, created_at"),
    ("messages_tenant_campaign", "messages", "tenant_id, campaign_id"),
    ("platform_audit_business", "platform_audit", "business_id"),
    ("promo_codes_plan", "promo_codes", "tenant_id, plan_id"),
    ("quote_lines_tenant_quote", "quote_lines", "tenant_id, quote_id"),
    ("reviews_tenant_client", "reviews", "tenant_id, client_id"),
    ("reviews_service", "reviews", "service_id"),
    ("service_rooms_service", "service_rooms", "tenant_id, service_id"),
    ("session_series_location_room", "session_series", "tenant_id, location_id, room_id"),
    ("session_series_instructor", "session_series", "tenant_id, instructor_user_id"),
    ("sessions_location_room", "sessions", "tenant_id, location_id, room_id"),
    ("sessions_series", "sessions", "tenant_id, series_id"),
    ("sessions_address", "sessions", "address_id"),
    ("shifts_location_station", "shifts", "tenant_id, location_id, station_id"),
    ("tenant_members_custom_role", "tenant_members", "tenant_id, custom_role_id"),
    ("time_off_requests_tenant_user", "time_off_requests", "tenant_id, user_id, starts_on"),
    ("time_off_requests_time_off", "time_off_requests", "time_off_id"),
    ("tenant_members_home_location", "tenant_members", "tenant_id, home_location_id"),
    ("time_entries_bill", "time_entries", "bill_id"),
]

# Older indexes whose columns are a prefix of a new one above.
REPLACED: list[tuple[str, str, str]] = [
    ("bookings_client_idx", "bookings", "tenant_id, client_id"),
    ("sessions_location", "sessions", "tenant_id, location_id"),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX {name} ON app.{table} ({columns})")
    for name, _table, _columns in REPLACED:
        op.execute(f"DROP INDEX app.{name}")


def downgrade() -> None:
    for name, table, columns in REPLACED:
        op.execute(f"CREATE INDEX {name} ON app.{table} ({columns})")
    for name, _table, _columns in INDEXES:
        op.execute(f"DROP INDEX app.{name}")
