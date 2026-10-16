"""Business files area (round 6, F1).

- `app.file_folders`: a business's folders. The system folders (payroll slips, employees,
  business documents, imports, general) are created per business by the API and can't be
  removed; the business adds its own below them. Each folder says which permission opens it
  (`read_permission`) and which one adds files by hand (`write_permission`, null = only the
  system adds files there), and whether its files are kept (`retain`: archived, never deleted,
  for accounting papers) and sealed (`sensitive`: encrypted at rest).
- `app.business_files`: the files. The bytes go through the storage provider (decision T80);
  a file can belong to one employee (`owner_user_id`, shown in their "My documents"), to one
  branch (`location_id`) and can expire (`expires_at`, the imports folder keeps files 30 days).
- The business's space allowance now counts these files too (`app.storage_used`).

Revision ID: 0104
Revises: 0103
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0104"
down_revision: str | None = "0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_FILE = 10 * 1024 * 1024
SYSTEM_KEYS = ("payroll", "employees", "business_docs", "imports", "general")


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.file_folders (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            parent_id         uuid,
            name              text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
            system_key        text CHECK (system_key IN {SYSTEM_KEYS!r}),
            read_permission   text NOT NULL DEFAULT 'files.read'
                              CHECK (length(read_permission) <= 60),
            write_permission  text CHECK (length(write_permission) <= 60),
            retain            boolean NOT NULL DEFAULT false,
            sensitive         boolean NOT NULL DEFAULT false,
            created_by        uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, parent_id) REFERENCES app.file_folders (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX file_folders_system ON app.file_folders (tenant_id, system_key)
        WHERE system_key IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX file_folders_name ON app.file_folders
            (tenant_id, coalesce(parent_id, '00000000-0000-0000-0000-000000000000'), lower(name))
    """)
    op.execute(f"""
        CREATE TABLE app.business_files (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            folder_id      uuid NOT NULL,
            name           text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
            content_type   text NOT NULL CHECK (length(content_type) <= 120),
            size           integer NOT NULL CHECK (size BETWEEN 1 AND {MAX_FILE}),
            content        bytea,
            storage_key    text CHECK (length(storage_key) <= 500),
            encrypted      boolean NOT NULL DEFAULT false,
            owner_user_id  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            location_id    uuid REFERENCES app.locations (id) ON DELETE SET NULL,
            archived_at    timestamptz,
            expires_at     timestamptz,
            created_by     uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at     timestamptz NOT NULL DEFAULT now(),
            CHECK ((content IS NULL) <> (storage_key IS NULL)),
            FOREIGN KEY (tenant_id, folder_id) REFERENCES app.file_folders (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX business_files_folder ON app.business_files (tenant_id, folder_id)")
    op.execute("CREATE INDEX business_files_owner ON app.business_files (owner_user_id)")
    op.execute("CREATE INDEX business_files_location ON app.business_files (location_id)")
    op.execute("CREATE INDEX file_folders_parent ON app.file_folders (tenant_id, parent_id)")
    for table in ("file_folders", "business_files"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)

    # A signed link (checked by the API) opens one file on a phone, which can't send the sign-in.
    op.execute("""
        CREATE FUNCTION app.business_file(p_file uuid, p_tenant uuid)
        RETURNS TABLE (name text, content_type text, content bytea, storage_key text,
                       encrypted boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT f.name, f.content_type, f.content, f.storage_key, f.encrypted
            FROM app.business_files f WHERE f.id = p_file AND f.tenant_id = p_tenant
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.business_file(uuid, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.business_file(uuid, uuid) TO app_api")

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


def downgrade() -> None:
    op.execute("DROP FUNCTION app.business_file(uuid, uuid)")
    op.execute("""
        CREATE OR REPLACE FUNCTION app.storage_used() RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT coalesce(sum(d.size), 0)::bigint FROM app.client_documents d
            WHERE d.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
        $$
    """)
    op.execute("DROP TABLE app.business_files")
    op.execute("DROP TABLE app.file_folders")
