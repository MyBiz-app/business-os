"""A team member assigned to branches works only in them (#64, decision X19).

The API sets `app.location_ids` to the member's branches when they have no branch selected,
so "all branches" means all of theirs; `app.in_branch` filters lists and numbers by it.
Owners and managers, and members with no branches assigned, are unaffected.

Revision ID: 0056
Revises: 0055
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION app.in_branch(p_location uuid) RETURNS boolean
        LANGUAGE sql STABLE SET search_path = ''
        AS $$
            SELECT CASE
                WHEN app.current_location_id() IS NOT NULL
                    THEN p_location = app.current_location_id()
                WHEN nullif(current_setting('app.location_ids', true), '') IS NOT NULL
                    THEN p_location = ANY(current_setting('app.location_ids', true)::uuid[])
                ELSE true
            END
        $$
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION app.in_branch(p_location uuid) RETURNS boolean
        LANGUAGE sql STABLE SET search_path = ''
        AS $$
            SELECT app.current_location_id() IS NULL OR p_location = app.current_location_id()
        $$
    """)
