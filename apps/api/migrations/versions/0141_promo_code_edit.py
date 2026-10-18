"""Let the API edit a promo code, not only pause it (round 7, R20).

Expand step, grants only: `app_api` could update just `active` on `app.promo_codes` (0035). It
may now also update the discount, the plan, the dates and the use limit. The code text and the
tenant stay fixed. The API refuses a new discount amount once a paid checkout used the code.

Revision ID: 0141
Revises: 0138
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0141"
down_revision: str | None = "0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = "active, percent_off, amount_off, plan_id, starts_on, ends_on, max_uses"


def upgrade() -> None:
    op.execute(f"GRANT UPDATE ({COLUMNS}) ON app.promo_codes TO app_api")


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (percent_off, amount_off, plan_id, starts_on, ends_on, max_uses) "
        "ON app.promo_codes FROM app_api"
    )
