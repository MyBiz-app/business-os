"""Account status: quiet reminders instead of banners (CRM Premium W2-1).

The two-step sign-in and home address reminders become a dot by the person's picture and a card on
the home page. Two columns on `app.users` remember the person's answers: "remind me in a week"
(`mfa_reminder_snoozed_until`) and "skip" for the home address (`address_reminder_skipped_at`).

`app.mfa_risk_acknowledgements.source` records where the person confirmed the warning: in their
security settings, by choosing "I don't want two-step sign-in" (`opt_out`), or in the window that
opens at a sensitive action (`sensitive_action`). Rows written before this migration say `settings`.

Revision ID: 0152
Revises: 0151
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0152"
down_revision: str | None = "0151"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.users
            ADD COLUMN mfa_reminder_snoozed_until timestamptz,
            ADD COLUMN address_reminder_skipped_at timestamptz
    """)
    op.execute("""
        ALTER TABLE app.mfa_risk_acknowledgements
            ADD COLUMN source text NOT NULL DEFAULT 'settings'
                CHECK (source IN ('settings', 'opt_out', 'sensitive_action'))
    """)


def downgrade() -> None:
    # contract: only a rollback drops the columns this migration added; the previous release never
    # reads them (it inserts acknowledgements without `source`).
    op.execute("ALTER TABLE app.mfa_risk_acknowledgements DROP COLUMN source")
    op.execute("""
        ALTER TABLE app.users
            DROP COLUMN address_reminder_skipped_at,
            DROP COLUMN mfa_reminder_snoozed_until
    """)
