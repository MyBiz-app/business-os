"""Cancellation policy and plans with a quota per period (round 7, R32).

Expand step. A business gets a cancellation policy in three layers (the business, a service, a
plan; the most specific one wins): how long before the session a client may cancel for free, what a
late cancellation and a no-show cost (`counts` as a used visit, `recorded` only, or a `fee` that is
built but kept off until payments are on), and the optional limit of no-shows before the app stops
booking. A membership plan can say "N visits per week" or "per month" (`period_quota`,
`period_unit`), copied to the entitlement when it is sold. A booking can have its visit given back
by a manager (`credit_released`, with who, when and why).

Nothing existing changes: a business with no policy row keeps its one cancellation window and a
late cancellation still counts as used; a plan with no quota is unlimited as before; the previous
release never selects the new columns and a booking's `credit_released` defaults to false.

Revision ID: 0138
Revises: 0137
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0138"
down_revision: str | None = "0137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFICATION_KINDS = (
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
    "plan_ending",
    "friend_request",
    "class_invite",
    "waitlist_spot_open",
    "waitlist_spot_taken",
    "freeze_approved",
    "freeze_rejected",
)
NEW_KINDS = ("credit_returned",)


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


# The first day of the week or month that holds `p_day`. A week starts on Sunday (`p_week_start`
# 0) or Monday (1).
PERIOD_START = """
    CREATE FUNCTION app.period_start(p_day date, p_unit text, p_week_start integer)
    RETURNS date
    LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = ''
    AS $$
        SELECT CASE p_unit
            WHEN 'week' THEN p_day - ((extract(dow FROM p_day)::integer - p_week_start + 7) % 7)
            WHEN 'month' THEN date_trunc('month', p_day)::date
        END
    $$
"""

# How many visits of this entitlement count in the week or month that holds `p_day`: bookings that
# were not cancelled in time (or were cancelled late and still count), minus visits given back.
QUOTA_USED = """
    CREATE FUNCTION app.quota_used(p_entitlement_id uuid, p_day date)
    RETURNS integer
    LANGUAGE sql STABLE SET search_path = ''
    AS $$
        SELECT count(*)::integer
        FROM app.entitlements e
        JOIN app.tenants t ON t.id = e.tenant_id
        CROSS JOIN LATERAL (
            SELECT CASE WHEN t.locale = 'he' THEN 0 ELSE 1 END AS week_start
        ) w
        JOIN app.bookings b ON b.entitlement_id = e.id
        JOIN app.sessions s ON s.id = b.session_id
        WHERE e.id = p_entitlement_id AND e.period_unit IS NOT NULL
          AND b.status <> 'waitlisted' AND (b.status <> 'cancelled' OR b.late_cancel)
          AND NOT b.credit_released
          AND app.period_start((s.starts_at AT TIME ZONE t.time_zone)::date,
                               e.period_unit, w.week_start)
              = app.period_start(p_day, e.period_unit, w.week_start)
    $$
"""

# The terms that apply to a booking into this session that uses this entitlement (or none): the
# plan's policy if it has one, else the service's, else the business's (its window for a class, an
# appointment or a court or room), else the business's one old window with "counts as used".
CANCELLATION_TERMS = """
    CREATE FUNCTION app.cancellation_terms(p_session_id uuid, p_entitlement_id uuid)
    RETURNS TABLE (
        free_minutes integer, late_outcome text, no_show_outcome text, no_show_limit integer,
        source text
    )
    LANGUAGE sql STABLE SET search_path = ''
    AS $$
        WITH ctx AS (
            SELECT s.tenant_id, s.service_id, s.reserved, s.capacity,
                   t.cancellation_window_minutes AS legacy
            FROM app.sessions s JOIN app.tenants t ON t.id = s.tenant_id
            WHERE s.id = p_session_id
        ), options AS (
            SELECT 1 AS rank, 'plan' AS source, cp.free_minutes, cp.late_outcome,
                   cp.no_show_outcome, cp.no_show_limit
            FROM ctx, app.entitlements e
            JOIN app.cancellation_policies cp ON cp.scope = 'plan' AND cp.plan_id = e.plan_id
            WHERE e.id = p_entitlement_id
            UNION ALL
            SELECT 2, 'service', cp.free_minutes, cp.late_outcome, cp.no_show_outcome,
                   cp.no_show_limit
            FROM ctx
            JOIN app.cancellation_policies cp
                ON cp.scope = 'service' AND cp.service_id = ctx.service_id
            UNION ALL
            SELECT 3, 'business',
                   CASE WHEN ctx.reserved THEN cp.resource_minutes
                        WHEN ctx.capacity > 1 THEN cp.group_minutes
                        ELSE cp.personal_minutes END,
                   cp.late_outcome, cp.no_show_outcome, cp.no_show_limit
            FROM ctx
            JOIN app.cancellation_policies cp
                ON cp.scope = 'business' AND cp.tenant_id = ctx.tenant_id
            UNION ALL
            SELECT 4, 'legacy', ctx.legacy, 'counts', 'counts', NULL FROM ctx
        )
        SELECT o.free_minutes, o.late_outcome, o.no_show_outcome, o.no_show_limit, o.source
        FROM options o ORDER BY o.rank LIMIT 1
    $$
"""

# Every way an entitlement is created (sold by staff, bought in the app, from a quote, imported)
# gets the plan's quota without each of them having to copy it.
COPY_PERIOD = """
    CREATE FUNCTION app.entitlements_copy_period() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $$
    BEGIN
        IF NEW.period_quota IS NULL AND NEW.plan_id IS NOT NULL THEN
            SELECT p.period_quota, p.period_unit INTO NEW.period_quota, NEW.period_unit
            FROM app.plans p WHERE p.tenant_id = NEW.tenant_id AND p.id = NEW.plan_id;
        END IF;
        RETURN NEW;
    END
    $$
"""


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.plans
            ADD COLUMN period_quota integer
                CONSTRAINT plans_period_quota_check CHECK (period_quota BETWEEN 1 AND 100),
            ADD COLUMN period_unit text
                CONSTRAINT plans_period_unit_check CHECK (period_unit IN ('week', 'month')),
            ADD CONSTRAINT plans_period_shape CHECK (
                (period_quota IS NULL AND period_unit IS NULL)
                OR (period_quota IS NOT NULL AND period_unit IS NOT NULL AND kind = 'membership')
            )
    """)
    op.execute("""
        ALTER TABLE app.entitlements
            ADD COLUMN period_quota integer
                CONSTRAINT entitlements_period_quota_check CHECK (period_quota BETWEEN 1 AND 100),
            ADD COLUMN period_unit text
                CONSTRAINT entitlements_period_unit_check CHECK (period_unit IN ('week', 'month')),
            ADD CONSTRAINT entitlements_period_shape CHECK (
                (period_quota IS NULL) = (period_unit IS NULL)
            )
    """)
    op.execute("""
        ALTER TABLE app.bookings
            ADD COLUMN credit_released boolean NOT NULL DEFAULT false,
            ADD COLUMN waived_by uuid REFERENCES app.users (id) ON DELETE SET NULL,
            ADD COLUMN waived_at timestamptz,
            ADD COLUMN waive_reason text CHECK (char_length(waive_reason) <= 300)
    """)
    op.execute(
        "CREATE INDEX bookings_waived_idx ON app.bookings (tenant_id, client_id, waived_at)"
        " WHERE waived_at IS NOT NULL"
    )

    op.execute("""
        CREATE TABLE app.cancellation_policies (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            scope             text NOT NULL CHECK (scope IN ('business', 'service', 'plan')),
            service_id        uuid REFERENCES app.services (id) ON DELETE CASCADE,
            plan_id           uuid,
            group_minutes     integer CHECK (group_minutes BETWEEN 0 AND 10080),
            personal_minutes  integer CHECK (personal_minutes BETWEEN 0 AND 10080),
            resource_minutes  integer CHECK (resource_minutes BETWEEN 0 AND 10080),
            free_minutes      integer CHECK (free_minutes BETWEEN 0 AND 10080),
            late_outcome      text NOT NULL DEFAULT 'counts'
                              CHECK (late_outcome IN ('counts', 'recorded', 'fee')),
            no_show_outcome   text NOT NULL DEFAULT 'counts'
                              CHECK (no_show_outcome IN ('counts', 'recorded', 'fee')),
            no_show_limit     integer CHECK (no_show_limit BETWEEN 1 AND 30),
            confirmed         boolean NOT NULL DEFAULT false,
            updated_at        timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, plan_id) REFERENCES app.plans (tenant_id, id)
                ON DELETE CASCADE,
            CHECK (
                (scope = 'business' AND service_id IS NULL AND plan_id IS NULL
                    AND group_minutes IS NOT NULL AND personal_minutes IS NOT NULL
                    AND resource_minutes IS NOT NULL AND free_minutes IS NULL)
                OR (scope = 'service' AND service_id IS NOT NULL AND plan_id IS NULL
                    AND free_minutes IS NOT NULL AND group_minutes IS NULL
                    AND personal_minutes IS NULL AND resource_minutes IS NULL)
                OR (scope = 'plan' AND plan_id IS NOT NULL AND service_id IS NULL
                    AND free_minutes IS NOT NULL AND group_minutes IS NULL
                    AND personal_minutes IS NULL AND resource_minutes IS NULL)
            )
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX cancellation_policies_business ON app.cancellation_policies"
        " (tenant_id) WHERE scope = 'business'"
    )
    op.execute(
        "CREATE UNIQUE INDEX cancellation_policies_service ON app.cancellation_policies"
        " (tenant_id, service_id) WHERE scope = 'service'"
    )
    op.execute(
        "CREATE UNIQUE INDEX cancellation_policies_plan ON app.cancellation_policies"
        " (tenant_id, plan_id) WHERE scope = 'plan'"
    )
    op.execute(
        "CREATE INDEX cancellation_policies_service_fk ON app.cancellation_policies (service_id)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.cancellation_policies TO app_api")
    op.execute("ALTER TABLE app.cancellation_policies ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY cancellation_policies_tenant ON app.cancellation_policies TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # A client reads the business's policy: the terms shown before booking and cancelling.
    op.execute("""
        CREATE POLICY cancellation_policies_client_select ON app.cancellation_policies
        FOR SELECT TO app_api USING (tenant_id = app.client_tenant_id())
    """)

    op.execute(COPY_PERIOD)
    op.execute("REVOKE ALL ON FUNCTION app.entitlements_copy_period() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER entitlements_copy_period BEFORE INSERT ON app.entitlements
        FOR EACH ROW EXECUTE FUNCTION app.entitlements_copy_period()
    """)
    op.execute(PERIOD_START)
    op.execute(QUOTA_USED)
    op.execute(CANCELLATION_TERMS)
    for signature in (
        "period_start(date, text, integer)",
        "quota_used(uuid, date)",
        "cancellation_terms(uuid, uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_api")

    _kinds_check((*NOTIFICATION_KINDS, *NEW_KINDS))


def downgrade() -> None:
    # contract: only the downgrade removes the policy table, functions and columns, which no
    # earlier release reads or calls.
    op.execute("DELETE FROM app.notifications WHERE kind = 'credit_returned'")
    _kinds_check(NOTIFICATION_KINDS)
    op.execute("DROP TRIGGER entitlements_copy_period ON app.entitlements")
    op.execute("DROP FUNCTION app.entitlements_copy_period()")
    op.execute("DROP FUNCTION app.cancellation_terms(uuid, uuid)")
    op.execute("DROP FUNCTION app.quota_used(uuid, date)")
    op.execute("DROP FUNCTION app.period_start(date, text, integer)")
    op.execute("DROP TABLE app.cancellation_policies")
    op.execute("DROP INDEX app.bookings_waived_idx")
    op.execute("""
        ALTER TABLE app.bookings
            DROP COLUMN waive_reason, DROP COLUMN waived_at, DROP COLUMN waived_by,
            DROP COLUMN credit_released
    """)
    op.execute("""
        ALTER TABLE app.entitlements
            DROP CONSTRAINT entitlements_period_shape,
            DROP COLUMN period_unit, DROP COLUMN period_quota
    """)
    op.execute("""
        ALTER TABLE app.plans
            DROP CONSTRAINT plans_period_shape,
            DROP COLUMN period_unit, DROP COLUMN period_quota
    """)
