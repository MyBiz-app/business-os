"""Open-ended weekly series: extended ahead automatically by a daily job.

A series created without an end date is open-ended. Its occurrences are generated a fixed
horizon ahead (12 weeks) and a daily job (`python -m app.jobs extend-series`) keeps that
horizon; `ends_on` is how far occurrences currently exist. Ending a series turns this off.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.session_series ADD COLUMN open_ended boolean NOT NULL DEFAULT false"
    )
    # Series created before this used a 12-week default when no end date was given.
    op.execute("UPDATE app.session_series SET open_ended = true WHERE ends_on - starts_on = 84")


def downgrade() -> None:
    op.execute("ALTER TABLE app.session_series DROP COLUMN open_ended")
