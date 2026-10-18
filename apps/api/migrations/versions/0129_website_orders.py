"""MyBiz Sites: website orders, the console board's functions and daily visit counts (round 7, R24).

Expand step, all new objects:
- `app.website_orders`: one order per business. The business fills in a brief (the 8 step
  wizard, saved as a draft after each step) and submits it; MyBiz moves it along the board
  (`briefing` -> `received` -> `building` -> `review` -> `live`). `snapshot` is what MyBiz knew
  about the business when the brief was submitted (name, branches, services), so the build
  prompt needs nothing else. Prices are copied from the price list when the order is submitted.
- `app.website_visits_daily`: one count per business, day and source, written by a tiny
  tracking call from the finished site (no cookies, nothing personal).
- The files area gets a system folder "website" for the wizard's images (the key list of
  `file_folders.system_key` is widened; the previous release never writes the new key).
- Console functions (`businesses.act`): the board, one order's update and the order's files.
  Going `live` copies the site address to the business (`tenants.website_url`).

Revision ID: 0129
Revises: 0128
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0129"
down_revision: str | None = "0128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGES = "'briefing', 'received', 'building', 'review', 'live'"
SYSTEM_KEYS = ("payroll", "employees", "business_docs", "imports", "website", "general")
FUNCTIONS = (
    "platform_website_orders()",
    "platform_website_order_update(uuid, text, text, text, text)",
    "platform_website_order_files(uuid)",
    "website_track_visit(text, text)",
)


def upgrade() -> None:
    op.execute("ALTER TABLE app.file_folders DROP CONSTRAINT file_folders_system_key_check")
    op.execute(f"""
        ALTER TABLE app.file_folders ADD CONSTRAINT file_folders_system_key_check
            CHECK (system_key IN {SYSTEM_KEYS!r})
    """)
    op.execute(f"""
        CREATE TABLE app.website_orders (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL UNIQUE REFERENCES app.tenants (id) ON DELETE CASCADE,
            product          text NOT NULL
                                  CHECK (product IN ('landing_only', 'landing_with_system')),
            stage            text NOT NULL DEFAULT 'briefing'
                                  CHECK (stage IN ({STAGES})),
            brief            jsonb NOT NULL DEFAULT '{{}}'
                                  CHECK (pg_column_size(brief) <= 60000),
            snapshot         jsonb NOT NULL DEFAULT '{{}}'
                                  CHECK (pg_column_size(snapshot) <= 60000),
            tracking_key     text NOT NULL UNIQUE
                                  DEFAULT replace(gen_random_uuid()::text, '-', ''),
            currency         char(3) NOT NULL,
            setup_price      integer CHECK (setup_price >= 0),
            monthly_price    integer CHECK (monthly_price >= 0),
            site_url         text CHECK (site_url ~ '^https?://[^[:space:]]+$'
                                         AND length(site_url) <= 300),
            internal_notes   text CHECK (length(internal_notes) <= 4000),
            customer_message text CHECK (length(customer_message) <= 2000),
            change_request   text CHECK (length(change_request) <= 2000),
            created_by       uuid REFERENCES app.users (id) ON DELETE SET NULL,
            submitted_at     timestamptz,
            approved_at      timestamptz,
            live_at          timestamptz,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX website_orders_created_by ON app.website_orders (created_by)")
    op.execute("CREATE INDEX website_orders_stage ON app.website_orders (stage, updated_at)")
    op.execute("""
        GRANT SELECT, INSERT,
              UPDATE (product, stage, brief, snapshot, currency, setup_price, monthly_price,
                      submitted_at, approved_at, change_request, updated_at)
        ON app.website_orders TO app_api
    """)
    op.execute("ALTER TABLE app.website_orders ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY website_orders_tenant ON app.website_orders TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("""
        CREATE TABLE app.website_visits_daily (
            tenant_id  uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            day        date NOT NULL,
            source     text NOT NULL CHECK (source IN ('direct', 'search', 'social', 'other')),
            visits     integer NOT NULL DEFAULT 0 CHECK (visits >= 0),
            PRIMARY KEY (tenant_id, day, source)
        )
    """)
    op.execute("GRANT SELECT ON app.website_visits_daily TO app_api")
    op.execute("ALTER TABLE app.website_visits_daily ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY website_visits_tenant ON app.website_visits_daily FOR SELECT TO app_api
        USING (tenant_id = app.current_tenant_id())
    """)

    # The finished site calls this (anonymous). An unknown key counts nothing; the API's rate
    # limit keeps one visitor from inflating the numbers.
    op.execute("""
        CREATE FUNCTION app.website_track_visit(p_key text, p_source text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid;
        BEGIN
            SELECT o.tenant_id INTO v_tenant FROM app.website_orders o
            WHERE o.tracking_key = p_key AND o.stage = 'live';
            IF v_tenant IS NULL THEN
                RETURN;
            END IF;
            INSERT INTO app.website_visits_daily (tenant_id, day, source, visits)
            VALUES (v_tenant, (now() AT TIME ZONE 'UTC')::date,
                    CASE WHEN p_source IN ('direct', 'search', 'social') THEN p_source
                         ELSE 'other' END, 1)
            ON CONFLICT (tenant_id, day, source)
            DO UPDATE SET visits = app.website_visits_daily.visits + 1;
        END
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_website_orders()
        RETURNS TABLE (id uuid, tenant_id uuid, tenant_name text, product text, stage text,
                       brief jsonb, snapshot jsonb, tracking_key text, currency text,
                       setup_price integer, monthly_price integer, site_url text,
                       internal_notes text, customer_message text, change_request text,
                       contact_email text, contact_name text, submitted_at timestamptz,
                       approved_at timestamptz, live_at timestamptz, updated_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('businesses.act') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT o.id, o.tenant_id, t.name, o.product, o.stage, o.brief, o.snapshot,
                   o.tracking_key, o.currency::text, o.setup_price, o.monthly_price, o.site_url,
                   o.internal_notes, o.customer_message, o.change_request,
                   u.email, u.full_name, o.submitted_at, o.approved_at, o.live_at, o.updated_at
            FROM app.website_orders o
            JOIN app.tenants t ON t.id = o.tenant_id
            LEFT JOIN app.users u ON u.id = o.created_by
            ORDER BY array_position(
                         ARRAY['briefing', 'received', 'building', 'review', 'live'], o.stage),
                     o.updated_at DESC
            LIMIT 300;
        END
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_website_order_update(
            p_id uuid, p_stage text, p_site_url text, p_notes text, p_message text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_order app.website_orders;
        BEGIN
            IF NOT app.platform_can('businesses.act') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            SELECT * INTO v_order FROM app.website_orders WHERE id = p_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            -- The board starts at "received": a brief still being written is the business's.
            IF p_stage IS NOT NULL AND (p_stage = 'briefing' OR v_order.stage = 'briefing') THEN
                RAISE EXCEPTION 'not_submitted' USING ERRCODE = 'P0001';
            END IF;
            IF coalesce(p_stage, v_order.stage) = 'live'
               AND coalesce(nullif(p_site_url, ''), v_order.site_url) IS NULL THEN
                RAISE EXCEPTION 'site_url_required' USING ERRCODE = 'P0001';
            END IF;
            UPDATE app.website_orders
            SET stage = coalesce(p_stage, stage),
                site_url = CASE WHEN p_site_url IS NULL THEN site_url
                                ELSE nullif(p_site_url, '') END,
                internal_notes = coalesce(p_notes, internal_notes),
                customer_message = coalesce(nullif(p_message, ''), customer_message),
                -- A new stage after the business asked for changes answers the request.
                change_request = CASE WHEN p_stage IS NOT NULL AND p_stage <> stage
                                      THEN NULL ELSE change_request END,
                live_at = CASE WHEN p_stage = 'live' AND stage <> 'live' THEN now()
                               ELSE live_at END,
                updated_at = now()
            WHERE id = p_id;
            IF p_stage = 'live' THEN
                UPDATE app.tenants
                SET website_url = (SELECT site_url FROM app.website_orders WHERE id = p_id),
                    updated_at = now()
                WHERE id = v_order.tenant_id;
            END IF;
            PERFORM app.platform_audit_add(
                'website_order.updated', v_order.tenant_id,
                jsonb_build_object('order', p_id, 'stage', p_stage));
        END
        $$
    """)

    op.execute("""
        CREATE FUNCTION app.platform_website_order_files(p_id uuid)
        RETURNS TABLE (id uuid, name text, content_type text, content bytea,
                       storage_key text, encrypted boolean)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.platform_can('businesses.act') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT f.id, f.name, f.content_type, f.content, f.storage_key, f.encrypted
            FROM app.website_orders o
            JOIN app.business_files f ON f.tenant_id = o.tenant_id
                 AND f.id IN (SELECT (i ->> 'file_id')::uuid
                              FROM jsonb_array_elements(coalesce(o.brief -> 'images', '[]')) i
                              WHERE i ->> 'file_id' ~ '^[0-9a-f-]{36}$')
            WHERE o.id = p_id AND f.archived_at IS NULL
            ORDER BY f.created_at
            LIMIT 100;
        END
        $$
    """)

    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DELETE FROM app.file_folders WHERE system_key = 'website'")
    op.execute("ALTER TABLE app.file_folders DROP CONSTRAINT file_folders_system_key_check")
    op.execute("""
        ALTER TABLE app.file_folders ADD CONSTRAINT file_folders_system_key_check
            CHECK (system_key IN ('payroll', 'employees', 'business_docs', 'imports', 'general'))
    """)
    # contract: both tables are created by this migration; the previous release never reads them
    op.execute("DROP TABLE app.website_visits_daily")
    op.execute("DROP TABLE app.website_orders")
