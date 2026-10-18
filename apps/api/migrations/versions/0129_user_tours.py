"""Which guided tours a person has seen (round 7, R7).

Expand step: one new table, `app.user_tours (user_id, tour_key)`. A tour is marked seen per person
(not per business), so someone who works in two businesses is not shown the same guide twice.
Nothing else changes, so the previous release keeps working. The rows hold no personal data
(a tour key and a time), so they are cleared only when the person's row is deleted.

Revision ID: 0129
Revises: 0128
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0129"
down_revision: str | None = "0128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.user_tours (
            user_id   uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            tour_key  text NOT NULL CHECK (tour_key ~ '^[a-z0-9_]{1,40}$'),
            seen_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, tour_key)
        )
    """)
    op.execute("GRANT SELECT, INSERT, DELETE ON app.user_tours TO app_api")
    op.execute("ALTER TABLE app.user_tours ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY user_tours_self ON app.user_tours TO app_api
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
    """)


def downgrade() -> None:
    # contract: only a rollback drops the table this migration added; no earlier version reads it
    op.execute("DROP TABLE app.user_tours")
