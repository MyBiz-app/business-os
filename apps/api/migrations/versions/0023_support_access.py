"""Audited support access: an owner lets platform support see the business, for a limited
time, read-only.

While a grant is active, a platform admin's requests for that business resolve
app.current_tenant_id() (so the business's row policies apply as for a member); the API gives
them a read-only permission set, makes every such transaction READ ONLY at the database level
and writes each request to the business's audit log, which the owner can read.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.support_grants (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            granted_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            expires_at  timestamptz NOT NULL,
            revoked_at  timestamptz,
            revoked_by  uuid REFERENCES app.users (id) ON DELETE SET NULL,
            CHECK (expires_at > created_at)
        )
    """)
    op.execute("CREATE INDEX support_grants_tenant_idx ON app.support_grants (tenant_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.support_grants TO app_api")
    op.execute("ALTER TABLE app.support_grants ENABLE ROW LEVEL SECURITY")
    # Only members manage grants (support itself never can: it is read-only).
    op.execute("""
        CREATE POLICY support_grants_members ON app.support_grants TO app_api
        USING (app.is_member(tenant_id)) WITH CHECK (app.is_member(tenant_id))
    """)
    op.execute("""
        CREATE FUNCTION app.support_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT g.tenant_id FROM app.support_grants g
            WHERE g.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND g.revoked_at IS NULL AND g.expires_at > now()
              AND app.is_platform_admin()
            LIMIT 1
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT coalesce(
                (SELECT m.tenant_id FROM app.tenant_members m
                 WHERE m.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                   AND m.user_id = app.current_user_id()),
                app.support_tenant_id()
            )
        $$
    """)
    # The business row itself is selected by membership; support may read it too.
    op.execute("""
        CREATE POLICY tenants_support_select ON app.tenants FOR SELECT TO app_api
        USING (id = app.support_tenant_id())
    """)
    # Platform admins see which businesses granted them access (for the console).
    op.execute("""
        CREATE FUNCTION app.my_support_grants()
        RETURNS TABLE (tenant_id uuid, tenant_name text, expires_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT g.tenant_id, t.name, max(g.expires_at)
            FROM app.support_grants g JOIN app.tenants t ON t.id = g.tenant_id
            WHERE app.is_platform_admin() AND g.revoked_at IS NULL AND g.expires_at > now()
            GROUP BY g.tenant_id, t.name
        $$
    """)
    for function in ("support_tenant_id()", "my_support_grants()"):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    op.execute("DROP POLICY tenants_support_select ON app.tenants")
    op.execute("""
        CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT m.tenant_id
            FROM app.tenant_members m
            WHERE m.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND m.user_id = app.current_user_id()
        $$
    """)
    op.execute("DROP FUNCTION app.my_support_grants()")
    op.execute("DROP FUNCTION app.support_tenant_id()")
    op.execute("DROP TABLE app.support_grants")
