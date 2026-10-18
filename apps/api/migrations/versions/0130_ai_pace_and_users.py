"""AI pace and AI users (round 7, R8).

Expand step, three optional settings: `tenant_members.ai_access` (the person's own switch for the
AI team; null: whatever their role gives), `tenant_members.ai_daily_percent` (the most of the
business's monthly credits one person may use in a day; null: the default, 15) and
`tenant_ai_settings.extra_ai_users` (paid "AI user" add-ons beyond the 3 or 10 the module
includes, each adding credits to the pool). Nothing existing changes: a member with no setting
behaves as before, and the previous release never selects the new columns.

Revision ID: 0130
Revises: 0129
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0130"
down_revision: str | None = "0127"  # re-chained on the real head before merge
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenant_members
            ADD COLUMN ai_access boolean,
            ADD COLUMN ai_daily_percent smallint
                CONSTRAINT tenant_members_ai_daily_percent_check
                CHECK (ai_daily_percent BETWEEN 1 AND 100)
    """)
    op.execute("""
        ALTER TABLE app.tenant_ai_settings
            ADD COLUMN extra_ai_users integer NOT NULL DEFAULT 0
                CONSTRAINT tenant_ai_settings_extra_ai_users_check
                CHECK (extra_ai_users BETWEEN 0 AND 200)
    """)


def downgrade() -> None:
    # contract: only the downgrade drops the three new columns, which no earlier release reads.
    op.execute("ALTER TABLE app.tenant_ai_settings DROP COLUMN extra_ai_users")
    op.execute("ALTER TABLE app.tenant_members DROP COLUMN ai_daily_percent, DROP COLUMN ai_access")
