"""Push notification tokens: which devices a signed-in person has registered.

One row per (person, device token). A person can sign in on several devices; a device that
changes hands is re-registered under the new person by the endpoint. Not tenant-scoped: the
token belongs to the person, whichever business they are acting in.

Revision ID: 0070
Revises: 0069
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.push_tokens (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            token       text NOT NULL,
            platform    text NOT NULL CHECK (platform IN ('ios', 'android')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, token)
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.push_tokens TO app_api")
    op.execute("ALTER TABLE app.push_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY push_tokens_self ON app.push_tokens TO app_api
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.push_tokens")
