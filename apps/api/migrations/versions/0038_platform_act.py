"""MyBiz staff who hold `businesses.act` can enter any business to fix things for its owner
(a complaint, a mistake), without waiting for a support grant.

Everything they do is written to the business's own audit log, so the owner sees it in their
settings exactly like support visits, and to MyBiz's console audit. Entering is not silent and
not anonymous. Staff without that permission still need the owner's support grant, which stays
read-only.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The business the staff member is working in right now, if they may work in businesses.
    op.execute("""
        CREATE FUNCTION app.platform_act_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.id FROM app.tenants t
            WHERE t.id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND app.platform_can('businesses.act')
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
                app.support_tenant_id(),
                app.platform_act_tenant_id()
            )
        $$
    """)
    # The business row itself is selected by membership; MyBiz staff working in it read it too.
    op.execute("""
        CREATE POLICY tenants_platform_act_select ON app.tenants FOR SELECT TO app_api
        USING (id = app.platform_act_tenant_id())
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_act_tenant_id() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_act_tenant_id() TO app_api")


def downgrade() -> None:
    op.execute("DROP POLICY tenants_platform_act_select ON app.tenants")
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
    op.execute("DROP FUNCTION app.platform_act_tenant_id()")
