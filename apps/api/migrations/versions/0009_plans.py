"""Plans and entitlements: what clients buy (memberships, punch cards) and what they own.

A plan is the catalog item. An entitlement is one client's purchase of it: valid between two
local dates, unlimited (membership) or with a number of credits (punch card). Credits are not
stored as a counter; they are the bookings that use the entitlement (booked, waitlisted,
attended, no-show, or cancelled late), so cancelling in time gives the credit back.
Freezing pauses an entitlement for a date range and extends its end date by the same length.

Payments are simulated until a payment provider is chosen (DECISIONS O1).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
        ADD COLUMN booking_requires_plan boolean NOT NULL DEFAULT false
    """)

    op.execute("""
        CREATE TABLE app.plans (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name           text NOT NULL CHECK (length(trim(name)) > 0),
            description    text,
            kind           text NOT NULL CHECK (kind IN ('membership', 'punch_card')),
            price_amount   integer NOT NULL CHECK (price_amount >= 0),
            price_currency char(3) NOT NULL,
            validity_days  integer NOT NULL CHECK (validity_days BETWEEN 1 AND 1095),
            credits        integer CHECK (credits BETWEEN 1 AND 1000),
            active         boolean NOT NULL DEFAULT true,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'punch_card') = (credits IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE TABLE app.entitlements (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id     uuid NOT NULL,
            plan_id       uuid NOT NULL,
            name          text NOT NULL,
            kind          text NOT NULL CHECK (kind IN ('membership', 'punch_card')),
            credits       integer CHECK (credits BETWEEN 1 AND 1000),
            starts_on     date NOT NULL,
            ends_on       date NOT NULL CHECK (ends_on >= starts_on),
            status        text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
            price_amount    integer NOT NULL CHECK (price_amount >= 0),
            price_currency  char(3) NOT NULL,
            sold_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            cancelled_at  timestamptz,
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, plan_id) REFERENCES app.plans (tenant_id, id)
        )
    """)
    op.execute(
        "CREATE INDEX entitlements_client_idx ON app.entitlements (tenant_id, client_id, ends_on)"
    )
    op.execute("""
        CREATE TABLE app.entitlement_freezes (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            entitlement_id  uuid NOT NULL,
            starts_on       date NOT NULL,
            ends_on         date NOT NULL CHECK (ends_on >= starts_on),
            reason          text,
            created_by      uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at      timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, entitlement_id) REFERENCES app.entitlements (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE app.payments (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id        uuid NOT NULL,
            entitlement_id   uuid,
            amount           integer NOT NULL CHECK (amount >= 0),
            currency         char(3) NOT NULL,
            status           text NOT NULL CHECK (status IN ('succeeded', 'failed', 'refunded')),
            provider         text NOT NULL,
            provider_ref     text,
            idempotency_key  text NOT NULL,
            created_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, idempotency_key),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, entitlement_id) REFERENCES app.entitlements (tenant_id, id)
                ON DELETE SET NULL (entitlement_id)
        )
    """)

    op.execute("ALTER TABLE app.bookings ADD COLUMN entitlement_id uuid")
    op.execute("""
        ALTER TABLE app.bookings ADD CONSTRAINT bookings_entitlement_fkey
        FOREIGN KEY (tenant_id, entitlement_id) REFERENCES app.entitlements (tenant_id, id)
            ON DELETE SET NULL (entitlement_id)
    """)
    op.execute("CREATE INDEX bookings_entitlement_idx ON app.bookings (entitlement_id)")

    for table in ("plans", "entitlements", "entitlement_freezes", "payments"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)
    # Clients see the business's active plans and their own entitlements and freezes.
    op.execute("""
        CREATE POLICY plans_client_select ON app.plans FOR SELECT TO app_api
        USING (tenant_id = app.client_tenant_id() AND active)
    """)
    op.execute("""
        CREATE POLICY entitlements_client_select ON app.entitlements FOR SELECT TO app_api
        USING (client_id = app.current_client_id())
    """)
    op.execute("""
        CREATE POLICY entitlement_freezes_client_select ON app.entitlement_freezes
        FOR SELECT TO app_api
        USING (EXISTS (
            SELECT 1 FROM app.entitlements e
            WHERE e.id = entitlement_id AND e.client_id = app.current_client_id()
        ))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app.bookings DROP COLUMN entitlement_id")
    op.execute("DROP TABLE app.payments, app.entitlement_freezes, app.entitlements, app.plans")
    op.execute("ALTER TABLE app.tenants DROP COLUMN booking_requires_plan")
