"""The business's own words (slice C3 of the categories and service model spec).

`tenants.terms_override` holds the words an owner changed for their business, by language and
word: `{"he": {"clients": "חברי המועדון"}, "en": {"clients": "Club members"}}`. A word that is
not listed keeps the industry's default, so an empty object changes nothing. The keys are
checked in the API against the list of words the screens know; the database only guarantees the
shape.

Revision ID: 0159
Revises: 0158
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0159"
down_revision: str | None = "0158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN terms_override jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(terms_override) = 'object')
    """)
    op.execute("GRANT UPDATE (terms_override) ON app.tenants TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops it, and the previous release never reads the column.
    op.execute("ALTER TABLE app.tenants DROP COLUMN terms_override")
