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


# Many tables point at a membership (appointments, shifts, reporting lines, ...), so the move is
# copy the membership to the demo account, repoint every reference, then drop the old one.
MOVE_MEMBERSHIPS = f"""
DO $$
DECLARE
    owner_id uuid;
    demo_id uuid;
    moving uuid[];
    cols text;
    fk record;
BEGIN
    SELECT id INTO owner_id FROM app.users WHERE lower(email) = '{PRIMARY_OWNER}';
    SELECT id INTO demo_id FROM app.users WHERE lower(email) = '{DEMO_ACCOUNT}';
    IF owner_id IS NULL OR demo_id IS NULL THEN
        RETURN;
    END IF;
    SELECT array_agg(m.tenant_id) INTO moving FROM app.tenant_members m
    WHERE m.user_id = owner_id AND NOT EXISTS (
        SELECT 1 FROM app.tenant_members x WHERE x.tenant_id = m.tenant_id AND x.user_id = demo_id
    );
    IF moving IS NULL THEN
        RETURN;
    END IF;

    SELECT string_agg(format('%I', column_name), ', ' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
    WHERE table_schema = 'app' AND table_name = 'tenant_members' AND column_name <> 'user_id';
    EXECUTE format(
        'INSERT INTO app.tenant_members (user_id, %1$s) SELECT %2$L, %1$s FROM app.tenant_members '
        'WHERE user_id = %3$L AND tenant_id = ANY (%4$L)', cols, demo_id, owner_id, moving);

    FOR fk IN
        SELECT c.conrelid::regclass AS tbl,
               (SELECT a.attname FROM pg_attribute a
                 WHERE a.attrelid = c.conrelid
                   AND a.attnum = c.conkey[array_position(c.confkey, u.attnum)]
               ) AS user_col,
               (SELECT a.attname FROM pg_attribute a
                 WHERE a.attrelid = c.conrelid
                   AND a.attnum = c.conkey[array_position(c.confkey, t.attnum)]
               ) AS tenant_col
        FROM pg_constraint c
        JOIN pg_attribute u ON u.attrelid = c.confrelid AND u.attname = 'user_id'
        JOIN pg_attribute t ON t.attrelid = c.confrelid AND t.attname = 'tenant_id'
        WHERE c.contype = 'f' AND c.confrelid = 'app.tenant_members'::regclass
          AND u.attnum = ANY (c.confkey) AND t.attnum = ANY (c.confkey)
    LOOP
        EXECUTE format('UPDATE %s SET %I = %L WHERE %I = %L AND %I = ANY (%L)',
                       fk.tbl, fk.user_col, demo_id, fk.user_col, owner_id, fk.tenant_col, moving);
    END LOOP;

    DELETE FROM app.tenant_members WHERE user_id = owner_id AND tenant_id = ANY (moving);
END
$$
"""


def upgrade() -> None:
    op.execute(MOVE_MEMBERSHIPS)


def downgrade() -> None:
    pass  # the move is not reversible: the original memberships are not recorded
