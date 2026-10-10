"""A person's own details: date of birth and home address.

Kept on `app.users` next to the phone number; all optional and visible only to the person
themselves (the existing owner-only row policy on `app.users` already covers the new columns).

Revision ID: 0062
Revises: 0061
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.users
            ADD COLUMN birth_date date CHECK (birth_date <= current_date),
            ADD COLUMN address_line text CHECK (char_length(address_line) <= 200),
            ADD COLUMN city text CHECK (char_length(city) <= 100),
            ADD COLUMN postal_code text CHECK (char_length(postal_code) <= 20)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE app.users
            DROP COLUMN birth_date, DROP COLUMN address_line,
            DROP COLUMN city, DROP COLUMN postal_code
    """)
