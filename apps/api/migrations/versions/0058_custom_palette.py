"""A person's own colors (docs/proposals/profile-crop-and-palette.md).

`app.users.palette` gains the value `custom`; the three picked colors (page background, text,
accent) are kept in their own columns, as `#rrggbb`, and stay when the person switches to a
preset. The API validates the format only: the app derives readable colors from the picks.

Revision ID: 0058
Revises: 0057
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEX = "'^#[0-9a-f]{6}$'"


def upgrade() -> None:
    op.execute("ALTER TABLE app.users DROP CONSTRAINT users_palette_check")
    op.execute(f"""
        ALTER TABLE app.users
            ADD CONSTRAINT users_palette_check
                CHECK (palette IN ('mybiz', 'ocean', 'forest', 'custom')),
            ADD COLUMN palette_background text CHECK (palette_background ~ {HEX}),
            ADD COLUMN palette_text text CHECK (palette_text ~ {HEX}),
            ADD COLUMN palette_accent text CHECK (palette_accent ~ {HEX}),
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
