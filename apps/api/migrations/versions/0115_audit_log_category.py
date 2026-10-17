"""Audit log screen for the owner (go-live, GL7).

`category` groups the entries for the filter on the owner's screen. It is derived from the first
part of the action (`staff.removed` is "team"), so every writer gets it without passing it, the old
entries included. The index serves the screen's filters and its keyset paging.

Revision ID: 0115
Revises: 0114
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0115"
down_revision: str | None = "0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.audit_log ADD COLUMN category text GENERATED ALWAYS AS (
            CASE split_part(action, '.', 1)
                WHEN 'staff' THEN 'team'
                WHEN 'role' THEN 'team'
                WHEN 'tenant' THEN 'settings'
                WHEN 'login' THEN 'security'
                WHEN 'mfa' THEN 'security'
                WHEN 'identity' THEN 'security'
                WHEN 'payroll' THEN 'payroll'
                WHEN 'clients' THEN 'privacy'
                WHEN 'export' THEN 'export'
                WHEN 'support' THEN 'support'
                WHEN 'platform' THEN 'support'
                ELSE 'other'
            END
        ) STORED
    """)
    op.execute(
        "CREATE INDEX audit_log_category_idx "
        "ON app.audit_log (tenant_id, category, occurred_at DESC, id DESC)"
    )
    op.execute("CREATE INDEX audit_log_actor_idx ON app.audit_log (tenant_id, actor_id)")


def downgrade() -> None:
    op.execute("DROP INDEX app.audit_log_actor_idx")
    op.execute("DROP INDEX app.audit_log_category_idx")
    op.execute("ALTER TABLE app.audit_log DROP COLUMN category")
