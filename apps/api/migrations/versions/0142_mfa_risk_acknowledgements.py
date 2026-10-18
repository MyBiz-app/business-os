"""Acknowledgements of the risk of working without two-step sign-in.

Two-step sign-in is optional for the people of a business. An owner or manager who has not turned
it on reads a warning and confirms they understand the risk; only then can they do the sensitive
actions (settings, pay, ID numbers, exports). One row per person and version of the warning:
when, and from where. The row belongs to the person, so it is not tenant-scoped, and rows are only
added.

Revision ID: 0142
Revises: 0141
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0142"
down_revision: str | None = "0141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.mfa_risk_acknowledgements (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            version         text NOT NULL,
            acknowledged_at timestamptz NOT NULL DEFAULT now(),
            ip_address      text NOT NULL DEFAULT '',
            user_agent      text NOT NULL DEFAULT '',
            UNIQUE (user_id, version)
        )
    """)
    op.execute("GRANT SELECT, INSERT ON app.mfa_risk_acknowledgements TO app_api")
    op.execute("ALTER TABLE app.mfa_risk_acknowledgements ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY mfa_risk_acknowledgements_self ON app.mfa_risk_acknowledgements TO app_api
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
    """)


def downgrade() -> None:
    # contract: only the downgrade drops the table this migration added; no earlier version uses it
    op.execute("DROP TABLE app.mfa_risk_acknowledgements")
