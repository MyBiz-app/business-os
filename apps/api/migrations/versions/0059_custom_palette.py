"""A person's own colors (docs/proposals/profile-crop-and-palette.md).

`app.users.palette` gains the value `custom`; the three picked colors (page background, text,
accent) are kept in their own columns, as `#rrggbb`, and stay when the person switches to a
preset. The API validates the format only: the app derives readable colors from the picks.

Revision ID: 0059
Revises: 0058
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEX = "'^#[0-9a-f]{6}$'"


def upgrade() -> None:
    # Written to be re-runnable: staging once recorded this palette change under the id 0058
    # (two branches used the same number), so its database has these columns but not the shift
    # planning ones that the real 0058 adds. Both are completed here whatever is already there;
    # on a database that went through 0058 in order, the first block changes nothing.
    op.execute("""
        ALTER TABLE app.tenant_members ADD COLUMN IF NOT EXISTS home_location_id uuid;
        ALTER TABLE app.tenant_members DROP CONSTRAINT IF EXISTS tenant_members_home_location_fkey;
        ALTER TABLE app.tenant_members
            ADD CONSTRAINT tenant_members_home_location_fkey
                FOREIGN KEY (tenant_id, home_location_id)
                REFERENCES app.locations (tenant_id, id) ON DELETE SET NULL (home_location_id);
        ALTER TABLE app.locations
            ADD COLUMN IF NOT EXISTS planning_cadence text NOT NULL DEFAULT 'weekly'
                CHECK (planning_cadence IN ('daily', 'weekly', 'monthly', 'custom')),
            ADD COLUMN IF NOT EXISTS planning_days integer
                CHECK (planning_days BETWEEN 1 AND 42);
        ALTER TABLE app.locations DROP CONSTRAINT IF EXISTS locations_planning_days_custom;
        ALTER TABLE app.locations
            ADD CONSTRAINT locations_planning_days_custom
                CHECK ((planning_cadence = 'custom') = (planning_days IS NOT NULL))
    """)
    op.execute("ALTER TABLE app.users DROP CONSTRAINT IF EXISTS users_palette_check")
    op.execute("ALTER TABLE app.users DROP CONSTRAINT IF EXISTS users_custom_palette_colors")
    op.execute(f"""
        ALTER TABLE app.users
            ADD CONSTRAINT users_palette_check
                CHECK (palette IN ('mybiz', 'ocean', 'forest', 'custom')),
            ADD COLUMN IF NOT EXISTS palette_background text CHECK (palette_background ~ {HEX}),
            ADD COLUMN IF NOT EXISTS palette_text text CHECK (palette_text ~ {HEX}),
            ADD COLUMN IF NOT EXISTS palette_accent text CHECK (palette_accent ~ {HEX}),
            ADD CONSTRAINT users_custom_palette_colors CHECK (
                palette IS DISTINCT FROM 'custom'
                OR (palette_background IS NOT NULL AND palette_text IS NOT NULL
                    AND palette_accent IS NOT NULL)
            )
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE app.users SET palette = NULL WHERE palette = 'custom';
        ALTER TABLE app.users
            DROP CONSTRAINT users_custom_palette_colors,
            DROP COLUMN palette_background, DROP COLUMN palette_text, DROP COLUMN palette_accent,
            DROP CONSTRAINT users_palette_check,
            ADD CONSTRAINT users_palette_check CHECK (palette IN ('mybiz', 'ocean', 'forest'))
    """)
