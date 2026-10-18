"""Sign-up tracks and business size (round 7, R25a).

Expand step only: two nullable-or-defaulted columns on `app.tenants` and one lookup function.

* `product_track`: `full` (the system, the default for every business that exists today) or
  `website_only` (a business that ordered a website and nothing else; it can add the system at
  any time without signing up again).
* `business_size`: how big the business said it is at sign-up (`solo`, `small` 2-5, `medium`
  6-20, `network`). Null for businesses created before the question was kept.
* `app.account_exists(email)`: lets the sign-up say "it looks like you already have an account"
  before a second business is opened. It answers yes or no only; the API rate-limits it.

# contract: only the downgrade drops anything (the columns and the function); the upgrade adds
# them and touches nothing that exists, so the previous API version keeps working.

Revision ID: 0134
Revises: 0133
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0134"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN product_track text NOT NULL DEFAULT 'full'
                CHECK (product_track IN ('full', 'website_only')),
            ADD COLUMN business_size text
                CHECK (business_size IN ('solo', 'small', 'medium', 'network'))
    """)
    op.execute("GRANT UPDATE (product_track, business_size) ON app.tenants TO app_api")
    op.execute("""
        CREATE FUNCTION app.account_exists(p_email text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT EXISTS (SELECT 1 FROM app.users WHERE lower(email) = lower(trim(p_email)))
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.account_exists(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.account_exists(text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.account_exists(text)")
    op.execute("ALTER TABLE app.tenants DROP COLUMN business_size, DROP COLUMN product_track")
