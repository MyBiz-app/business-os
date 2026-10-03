"""Custom roles: a business names a set of permissions (switches) and assigns it to members.

A member has a system role (`tenant_members.role`) and, optionally, a custom role that then
defines their permissions. Owners always keep the full owner role; a custom role can only be
given to non-owners.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.tenant_roles (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name         text NOT NULL CHECK (length(trim(name)) > 0),
            permissions  text[] NOT NULL DEFAULT '{}',
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX tenant_roles_name_key ON app.tenant_roles (tenant_id, lower(name))"
    )
    op.execute("ALTER TABLE app.tenant_members ADD COLUMN custom_role_id uuid")
    op.execute("""
        ALTER TABLE app.tenant_members
            ADD CONSTRAINT tenant_members_custom_role_fkey
                FOREIGN KEY (tenant_id, custom_role_id) REFERENCES app.tenant_roles (tenant_id, id),
            ADD CONSTRAINT tenant_members_owner_no_custom_role
                CHECK (custom_role_id IS NULL OR role <> 'owner')
    """)

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.tenant_roles TO app_api")
    op.execute("ALTER TABLE app.tenant_roles ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_roles_tenant ON app.tenant_roles TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenant_members
            DROP CONSTRAINT tenant_members_owner_no_custom_role,
            DROP CONSTRAINT tenant_members_custom_role_fkey,
            DROP COLUMN custom_role_id
    """)
    op.execute("DROP TABLE app.tenant_roles")
