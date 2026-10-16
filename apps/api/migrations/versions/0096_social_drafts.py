"""Post drafts the content agent (Shira) prepares for the owner.

A draft is only text (and a picture link) for one network. Publishing is a separate step the
owner confirms; the draft then keeps the link to the live post.

Revision ID: 0096
Revises: 0095
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0096"
down_revision: str | None = "0095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.social_drafts (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            network      text CHECK (length(network) BETWEEN 1 AND 40),
            body         text NOT NULL CHECK (length(body) BETWEEN 1 AND 2200),
            image_url    text CHECK (length(image_url) <= 2000),
            idea         text CHECK (length(idea) <= 300),
            status       text NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'published', 'discarded')),
            created_by   uuid,
            agent_key    text,
            external_id  text,
            permalink    text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            published_at timestamptz
        )
    """)
    op.execute(
        "CREATE INDEX social_drafts_tenant ON app.social_drafts (tenant_id, created_at DESC)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.social_drafts TO app_api")
    op.execute("ALTER TABLE app.social_drafts ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY social_drafts_tenant ON app.social_drafts TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.social_drafts")
