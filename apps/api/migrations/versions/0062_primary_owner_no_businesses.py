"""The MyBiz primary owner owns the platform, not businesses: re-home demo memberships.

The primary owner account only uses the MyBiz console. Any business membership it still holds
(left over from early demo seeding) moves to the separate demo account; nothing is deleted and
the other members of those businesses are untouched. A no-op when either account is missing.

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

PRIMARY_OWNER = "adire7399@gmail.com"
DEMO_ACCOUNT = "adiredri73@gmail.com"


MOVE_MEMBERSHIPS = f"""
        UPDATE app.tenant_members m
        SET user_id = demo.id
        FROM app.users owner, app.users demo
        WHERE lower(owner.email) = '{PRIMARY_OWNER}' AND m.user_id = owner.id
          AND lower(demo.email) = '{DEMO_ACCOUNT}'
          AND NOT EXISTS (
              SELECT 1 FROM app.tenant_members x
              WHERE x.tenant_id = m.tenant_id AND x.user_id = demo.id
          )
    """


def upgrade() -> None:
    op.execute(MOVE_MEMBERSHIPS)


def downgrade() -> None:
    pass  # the move is not reversible: the original memberships are not recorded
