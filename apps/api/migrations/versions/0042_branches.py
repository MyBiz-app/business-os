"""Branches across the business (decision T77): sales, plans sold and clients know their branch,
team members can be assigned to branches, and a request can carry a "current branch".

- `app.current_location_id()` is the branch the request works in (set by the API from the
  X-Location-Id header after checking it belongs to the business); `app.in_branch()` filters
  by it and lets everything through when no branch is selected.
- New sessions, payments, plans sold and clients get a branch when none is given: the current
  branch, else the client's home branch, else the business's only active branch.
- The extra-branch module follows the number of active branches (one is included).
- Every business has at least one branch: existing ones without any get a main branch, and
  existing rows of single-branch businesses are filed under that branch.

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, the client column used to fall back to the client's home branch)
FILED = (
    ("sessions", "location_id", None),
    ("payments", "location_id", "client_id"),
    ("entitlements", "location_id", "client_id"),
    ("clients", "home_location_id", None),
)


def upgrade() -> None:
    for table, column in (("payments", "location_id"), ("entitlements", "location_id"),
                          ("clients", "home_location_id")):  # fmt: skip
        op.execute(f"""
            ALTER TABLE app.{table} ADD COLUMN {column} uuid,
                ADD FOREIGN KEY (tenant_id, {column}) REFERENCES app.locations (tenant_id, id)
        """)
        op.execute(f"CREATE INDEX {table}_{column} ON app.{table} (tenant_id, {column})")
    op.execute("CREATE INDEX sessions_location ON app.sessions (tenant_id, location_id)")
    op.execute(
        "ALTER TABLE app.tenant_members ADD COLUMN location_ids uuid[] NOT NULL DEFAULT '{}'"
    )

    op.execute("""
        CREATE FUNCTION app.current_location_id() RETURNS uuid
        LANGUAGE sql STABLE SET search_path = ''
        AS $$ SELECT nullif(current_setting('app.location_id', true), '')::uuid $$
    """)
    # Filters lists and numbers by the current branch; no branch selected means all.
    op.execute("""
        CREATE FUNCTION app.in_branch(p_location uuid) RETURNS boolean
        LANGUAGE sql STABLE SET search_path = ''
        AS $$
            SELECT app.current_location_id() IS NULL OR p_location = app.current_location_id()
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.default_location_id(p_tenant uuid, p_client uuid) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT coalesce(
                (SELECT l.id FROM app.locations l
                 WHERE l.tenant_id = p_tenant AND l.id = app.current_location_id()),
                (SELECT c.home_location_id FROM app.clients c
                 WHERE c.tenant_id = p_tenant AND c.id = p_client),
                (SELECT min(l.id::text)::uuid FROM app.locations l
                 WHERE l.tenant_id = p_tenant AND l.active
                 HAVING count(*) = 1)
            )
        $$
    """)
    for table, column, client in FILED:
        client_value = f"NEW.{client}" if client else "NULL"
        op.execute(f"""
            CREATE FUNCTION app.file_{table}_under_branch() RETURNS trigger
            LANGUAGE plpgsql SET search_path = '' AS $$
            BEGIN
                IF NEW.{column} IS NULL THEN
                    NEW.{column} := app.default_location_id(NEW.tenant_id, {client_value});
                END IF;
                RETURN NEW;
            END
            $$
        """)
        op.execute(f"""
            CREATE TRIGGER file_under_branch BEFORE INSERT ON app.{table}
            FOR EACH ROW EXECUTE FUNCTION app.file_{table}_under_branch()
        """)

    # The extra-branch module follows the active branches (one is included).
    op.execute("""
        CREATE FUNCTION app.sync_extra_locations_for(p_tenant uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_extra integer;
        BEGIN
            SELECT greatest(count(*) - 1, 0) INTO v_extra
            FROM app.locations WHERE tenant_id = p_tenant AND active;
            IF v_extra = 0 THEN
                DELETE FROM app.tenant_modules
                WHERE tenant_id = p_tenant AND module_key = 'extra_location';
            ELSE
                INSERT INTO app.tenant_modules (tenant_id, module_key, quantity)
                VALUES (p_tenant, 'extra_location', least(v_extra, 50))
                ON CONFLICT (tenant_id, module_key) DO UPDATE SET quantity = EXCLUDED.quantity;
            END IF;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.sync_extra_locations() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            PERFORM app.sync_extra_locations_for(NEW.tenant_id);
            RETURN NULL;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER sync_extra_locations AFTER INSERT OR UPDATE OF active ON app.locations
        FOR EACH ROW EXECUTE FUNCTION app.sync_extra_locations()
    """)

    # Every business has a branch; single-branch businesses file their existing rows under it.
    op.execute("""
        INSERT INTO app.locations (tenant_id, name)
        SELECT t.id, CASE WHEN t.locale = 'he' THEN 'סניף ראשי' ELSE 'Main branch' END
        FROM app.tenants t
        WHERE NOT EXISTS (SELECT 1 FROM app.locations l WHERE l.tenant_id = t.id)
    """)
    for table, column, _ in FILED:
        op.execute(f"""
            UPDATE app.{table} x SET {column} = sole.id
            FROM (SELECT tenant_id, min(id::text)::uuid AS id FROM app.locations WHERE active
                  GROUP BY tenant_id HAVING count(*) = 1) sole
            WHERE x.tenant_id = sole.tenant_id AND x.{column} IS NULL
        """)

    functions = ("current_location_id()", "in_branch(uuid)", "default_location_id(uuid, uuid)",
                 "sync_extra_locations_for(uuid)")  # fmt: skip
    for function in functions:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    op.execute("DROP TRIGGER sync_extra_locations ON app.locations")
    op.execute("DROP FUNCTION app.sync_extra_locations()")
    op.execute("DROP FUNCTION app.sync_extra_locations_for(uuid)")
    for table, _, _ in FILED:
        op.execute(f"DROP TRIGGER file_under_branch ON app.{table}")
        op.execute(f"DROP FUNCTION app.file_{table}_under_branch()")
    op.execute("DROP FUNCTION app.default_location_id(uuid, uuid)")
    op.execute("DROP FUNCTION app.in_branch(uuid)")
    op.execute("DROP FUNCTION app.current_location_id()")
    op.execute("ALTER TABLE app.tenant_members DROP COLUMN location_ids")
    op.execute("DROP INDEX app.sessions_location")
    for table, column in (("payments", "location_id"), ("entitlements", "location_id"),
                          ("clients", "home_location_id")):  # fmt: skip
        op.execute(f"ALTER TABLE app.{table} DROP COLUMN {column}")
