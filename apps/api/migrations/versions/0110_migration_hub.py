"""Migration hub (round 6, M1): moving an existing business onto the platform.

- `app.import_sessions`: one move. The owner first confirms the right to transfer the data
  (`rights_confirmed_at`); `origin` says where the business comes from.
- `app.import_files`: the files of a move. The bytes live in the imports folder of the files area
  (kept 30 days, then purged, so `file_id` becomes null); each file has a `kind` (clients,
  memberships, services, staff, appointments) and the column-to-field `mapping` that was chosen.
- `app.import_batches`: one run of a move. It can be undone for 14 days (`undo_until`).
- `app.import_batch_items`: everything a batch created, so an undo removes exactly that.

Revision ID: 0110
Revises: 0106
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0110"
down_revision: str | None = "0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = ("clients", "memberships", "services", "staff", "appointments")
ENTITIES = ("client", "plan", "entitlement", "service", "invitation", "session", "booking")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.import_sessions (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            origin              text NOT NULL CHECK (length(origin) BETWEEN 1 AND 60),
            status              text NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft', 'imported', 'cancelled')),
            rights_confirmed_at timestamptz NOT NULL DEFAULT now(),
            created_by          uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    op.execute(f"""
        CREATE TABLE app.import_files (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            session_id  uuid NOT NULL,
            file_id     uuid REFERENCES app.business_files (id) ON DELETE SET NULL,
            filename    text NOT NULL CHECK (length(filename) BETWEEN 1 AND 200),
            kind        text CHECK (kind IN {KINDS!r}),
            headers     jsonb NOT NULL DEFAULT '[]',
            mapping     jsonb NOT NULL DEFAULT '[]',
            row_count   integer NOT NULL DEFAULT 0,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, session_id) REFERENCES app.import_sessions (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX import_files_session ON app.import_files (tenant_id, session_id)")
    op.execute("CREATE INDEX import_files_file ON app.import_files (file_id)")
    op.execute("""
        CREATE TABLE app.import_batches (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            session_id  uuid NOT NULL,
            status      text NOT NULL DEFAULT 'done' CHECK (status IN ('done', 'undone')),
            counts      jsonb NOT NULL DEFAULT '{}',
            undo_until  timestamptz NOT NULL,
            undone_at   timestamptz,
            created_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, session_id) REFERENCES app.import_sessions (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX import_batches_session ON app.import_batches (tenant_id, session_id)")
    op.execute(f"""
        CREATE TABLE app.import_batch_items (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            batch_id    uuid NOT NULL,
            entity      text NOT NULL CHECK (entity IN {ENTITIES!r}),
            entity_id   uuid NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, batch_id) REFERENCES app.import_batches (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX import_batch_items_batch ON app.import_batch_items (tenant_id, batch_id)"
    )
    for table in ("import_sessions", "import_files", "import_batches", "import_batch_items"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)

    # Undo removes what a batch created and nobody touched since (the API role can't delete
    # these rows itself). A row is "edited" when its `updated_at` moved past the import (or an
    # invitation was accepted); edited rows stay unless `p_include_edited`. A row that other
    # data still points at always stays, whatever the flag says, so no cascade removes data that
    # was added after the import. Children go first, so what the batch itself created below a
    # row is already gone when we reach it.
    op.execute("""
        CREATE FUNCTION app.undo_import_batch(p_batch uuid, p_include_edited boolean)
        RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid := app.current_tenant_id();
            v_removed jsonb := '{}';
            v_kept jsonb := '{}';
            v_step record;
            v_count integer;
            v_left integer;
            v_fk record;
            v_ids uuid[];
            v_found uuid[];
            v_blocked uuid[];
        BEGIN
            IF v_tenant IS NULL OR NOT EXISTS (
                SELECT 1 FROM app.import_batches
                WHERE id = p_batch AND tenant_id = v_tenant AND status = 'done'
            ) THEN
                RAISE EXCEPTION 'unknown batch' USING ERRCODE = '42501';
            END IF;

            FOR v_step IN
                SELECT * FROM (VALUES
                    ('booking', 'bookings', 't.updated_at > i.created_at'),
                    ('session', 'sessions', 't.updated_at > i.created_at'),
                    ('entitlement', 'entitlements',
                        't.updated_at > i.created_at OR t.status <> ''active'''),
                    ('plan', 'plans', 't.updated_at > i.created_at'),
                    ('invitation', 'invitations', 't.accepted_at IS NOT NULL'),
                    ('service', 'services', 't.updated_at > i.created_at'),
                    ('client', 'clients', 't.updated_at > i.created_at')
                ) AS s (entity, tbl, edited)
            LOOP
                -- Items whose row is already gone have nothing left to undo.
                EXECUTE format($q$
                    DELETE FROM app.import_batch_items i
                    WHERE i.batch_id = $1 AND i.tenant_id = $2 AND i.entity = $3
                      AND NOT EXISTS (SELECT 1 FROM app.%I t WHERE t.id = i.entity_id)
                $q$, v_step.tbl) USING p_batch, v_tenant, v_step.entity;

                SELECT coalesce(array_agg(entity_id), '{}') INTO v_ids
                FROM app.import_batch_items
                WHERE batch_id = p_batch AND tenant_id = v_tenant AND entity = v_step.entity;

                v_blocked := '{}';
                FOR v_fk IN
                    SELECT c.conrelid::regclass::text AS tbl, a.attname::text AS col
                    FROM pg_constraint c
                    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                    WHERE c.contype = 'f' AND c.confrelid = to_regclass('app.' || v_step.tbl)
                      AND a.attname <> 'tenant_id'
                      AND c.conrelid <> 'app.client_locations'::regclass  -- a list, not data
                LOOP
                    EXECUTE format(
                        'SELECT coalesce(array_agg(DISTINCT %I), ''{}'') FROM %s '
                        'WHERE %I = ANY ($1)', v_fk.col, v_fk.tbl, v_fk.col)
                    INTO v_found USING v_ids;
                    v_blocked := v_blocked || v_found;
                END LOOP;

                EXECUTE format($q$
                    WITH doomed AS (
                        SELECT i.id AS item_id, t.id AS row_id
                        FROM app.import_batch_items i
                        JOIN app.%1$I t ON t.id = i.entity_id AND t.tenant_id = i.tenant_id
                        WHERE i.batch_id = $1 AND i.tenant_id = $2 AND i.entity = $3
                          AND ($4 OR NOT (%2$s)) AND NOT (t.id = ANY ($5))
                    ), gone AS (
                        DELETE FROM app.%1$I WHERE id IN (SELECT row_id FROM doomed) RETURNING id
                    )
                    DELETE FROM app.import_batch_items
                    WHERE id IN (SELECT item_id FROM doomed)
                $q$, v_step.tbl, v_step.edited)
                USING p_batch, v_tenant, v_step.entity, p_include_edited, v_blocked;
                GET DIAGNOSTICS v_count = ROW_COUNT;

                SELECT count(*) INTO v_left FROM app.import_batch_items
                WHERE batch_id = p_batch AND tenant_id = v_tenant AND entity = v_step.entity;
                v_removed := v_removed || jsonb_build_object(v_step.entity, v_count);
                v_kept := v_kept || jsonb_build_object(v_step.entity, v_left);
            END LOOP;

            IF NOT EXISTS (SELECT 1 FROM app.import_batch_items
                           WHERE batch_id = p_batch AND tenant_id = v_tenant) THEN
                UPDATE app.import_batches SET status = 'undone', undone_at = now()
                WHERE id = p_batch AND tenant_id = v_tenant;
            END IF;
            RETURN jsonb_build_object('removed', v_removed, 'kept', v_kept);
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.undo_import_batch(uuid, boolean) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.undo_import_batch(uuid, boolean) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.undo_import_batch(uuid, boolean)")
    for table in ("import_batch_items", "import_batches", "import_files", "import_sessions"):
        op.execute(f"DROP TABLE app.{table}")
