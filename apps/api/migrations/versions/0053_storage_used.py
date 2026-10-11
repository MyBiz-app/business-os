"""How much file space a business uses, readable from a client's upload too (#104).

A client sees only their own documents (RLS), but the space limit is the business's, so this
function sums every document of the caller's business, staff or client.

Revision ID: 0053
Revises: 0052
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.storage_used() RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT coalesce(sum(d.size), 0)::bigint FROM app.client_documents d
            WHERE d.tenant_id = coalesce(app.current_tenant_id(), app.client_tenant_id())
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.storage_used() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.storage_used() TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.storage_used()")
