"""Plan quota alerts and product events (go-live, GL21).

- `quota_alerts`: the 80% and 100% marks a business's messages and space passed in a month,
  raised once each (like `ai_credit_alerts` for AI). They never block anything: messages keep
  going, and only new uploads stop at the space allowance (the owner's soft-quota decision).
- `storage_bytes(tenant)` counts every kept file, not only documents: logos, covers, branch logos,
  AI team pictures and issued documents. `storage_used()` is the current business's figure.
- `product_events`: what the owner needs to see where businesses drop out of sign-up. No personal
  data: an event name, a step, a random visitor id from the browser (before the business exists)
  and the business once it does. Visitors write sign-up steps through one function; a business's
  own events go in under row level security.
- Console functions (platform admins only): the sign-up funnel, active businesses per day and
  week, and the biggest consumers.

Revision ID: 0119
Revises: 0118
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0119"
down_revision: str | None = "0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.quota_alerts (
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            meter       text NOT NULL CHECK (meter IN ('messages', 'storage')),
            month_start date NOT NULL,
            threshold   integer NOT NULL CHECK (threshold IN (80, 100)),
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, meter, month_start, threshold)
        )
    """)
    op.execute("""
        CREATE TABLE app.product_events (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id   uuid REFERENCES app.tenants (id) ON DELETE CASCADE,
            visitor_id  uuid,
            event       text NOT NULL CHECK (event ~ '^[a-z_]{2,40}$'),
            step        text CHECK (step ~ '^[a-z_]{1,30}$'),
            properties  jsonb NOT NULL DEFAULT '{}' CHECK (pg_column_size(properties) <= 1000),
            occurred_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX product_events_event_idx ON app.product_events (event, occurred_at)")
    op.execute("CREATE INDEX product_events_tenant_idx ON app.product_events (tenant_id, event)")
    for table in ("quota_alerts", "product_events"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.quota_alerts TO app_api")
    op.execute("""
        CREATE POLICY quota_alerts_tenant ON app.quota_alerts TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # Nothing reads or writes the table directly: events go in through the functions below (a
    # business's own, a client's, a visitor's sign-up steps) and the console reads aggregates.
    op.execute("""
        CREATE FUNCTION app.record_event(
            p_event text, p_step text, p_once boolean, p_properties jsonb
        ) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            INSERT INTO app.product_events (tenant_id, event, step, properties)
            SELECT t.id, p_event, p_step, p_properties
            FROM (SELECT coalesce(app.current_tenant_id(), app.client_tenant_id()) AS id) t
            WHERE t.id IS NOT NULL AND (
                NOT p_once OR NOT EXISTS (
                    SELECT 1 FROM app.product_events e
                    WHERE e.tenant_id = t.id AND e.event = p_event
                )
            )
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.record_signup_step(p_visitor uuid, p_event text, p_step text)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            INSERT INTO app.product_events (visitor_id, event, step)
            SELECT p_visitor, p_event, p_step
            WHERE p_visitor IS NOT NULL AND p_event IN ('signup_started', 'signup_step')
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.storage_bytes(p_tenant uuid) RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT (
                SELECT coalesce(sum(d.size), 0) FROM app.client_documents d
                WHERE d.tenant_id = p_tenant
            ) + (
                SELECT coalesce(sum(f.size), 0) FROM app.business_files f
                WHERE f.tenant_id = p_tenant
            ) + (
                SELECT coalesce(octet_length(t.logo), 0) + coalesce(octet_length(t.cover), 0)
                FROM app.tenants t WHERE t.id = p_tenant
            ) + (
                SELECT coalesce(sum(octet_length(l.logo)), 0) FROM app.locations l
                WHERE l.tenant_id = p_tenant
            ) + (
                SELECT coalesce(sum(octet_length(a.content)), 0) FROM app.ai_agent_avatars a
                WHERE a.tenant_id = p_tenant
            ) + (
                SELECT coalesce(sum(octet_length(i.content)), 0) FROM app.issued_documents i
                WHERE i.tenant_id = p_tenant
            )
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app.storage_used() RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT app.storage_bytes(coalesce(app.current_tenant_id(), app.client_tenant_id()))
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_funnel(p_days integer)
        RETURNS TABLE (event text, step text, visitors bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT e.event, coalesce(e.step, ''),
                   count(DISTINCT coalesce(e.visitor_id::text, e.id::text))
            FROM app.product_events e
            WHERE e.event IN ('signup_started', 'signup_step', 'signup_completed')
              AND e.occurred_at > now() - make_interval(days => p_days)
            GROUP BY 1, 2;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_activity(p_days integer)
        RETURNS TABLE (day date, active_day integer, active_week integer)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            WITH acts AS (
                SELECT a.tenant_id, a.occurred_at::date AS d FROM app.audit_log a
                WHERE a.occurred_at > now() - make_interval(days => p_days + 7)
                UNION
                SELECT u.tenant_id, u.occurred_at::date FROM app.usage_events u
                WHERE u.occurred_at > now() - make_interval(days => p_days + 7)
                UNION
                SELECT e.tenant_id, e.occurred_at::date FROM app.product_events e
                WHERE e.tenant_id IS NOT NULL
                  AND e.occurred_at > now() - make_interval(days => p_days + 7)
            )
            SELECT g::date,
                   (SELECT count(DISTINCT x.tenant_id) FROM acts x WHERE x.d = g::date)::integer,
                   (SELECT count(DISTINCT x.tenant_id) FROM acts x
                    WHERE x.d BETWEEN g::date - 6 AND g::date)::integer
            FROM generate_series(current_date - (p_days - 1), current_date, '1 day') g
            ORDER BY 1;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_top_consumers(p_days integer, p_limit integer)
        RETURNS TABLE (tenant_id uuid, name text, messages numeric, ai_credits numeric,
                       storage_bytes bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT t.id, t.name,
                   coalesce(sum(u.quantity) FILTER (WHERE u.meter = 'messages'), 0),
                   coalesce(sum(u.quantity) FILTER (WHERE u.meter = 'ai_credits'), 0),
                   app.storage_bytes(t.id)
            FROM app.tenants t
            LEFT JOIN app.usage_events u
                   ON u.tenant_id = t.id AND u.occurred_at > now() - make_interval(days => p_days)
            GROUP BY t.id, t.name
            ORDER BY 3 DESC, 4 DESC, 5 DESC
            LIMIT least(greatest(p_limit, 1), 100);
        END
        $$
    """)
    for function in (
        "record_event(text, text, boolean, jsonb)",
        "record_signup_step(uuid, text, text)",
        "storage_bytes(uuid)",
        "platform_funnel(integer)",
        "platform_activity(integer)",
        "platform_top_consumers(integer, integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in (
        "platform_top_consumers(integer, integer)",
        "platform_activity(integer)",
        "platform_funnel(integer)",
    ):
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("""
        CREATE OR REPLACE FUNCTION app.storage_used() RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT (
                SELECT coalesce(sum(d.size), 0) FROM app.client_documents d
                WHERE d.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
            ) + (
                SELECT coalesce(sum(f.size), 0) FROM app.business_files f
                WHERE f.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
            )
        $$
    """)
    op.execute("DROP FUNCTION app.storage_bytes(uuid)")
    op.execute("DROP FUNCTION app.record_signup_step(uuid, text, text)")
    op.execute("DROP FUNCTION app.record_event(text, text, boolean, jsonb)")
    op.execute("DROP TABLE app.product_events")
    op.execute("DROP TABLE app.quota_alerts")
