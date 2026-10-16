"""Branch groups (round 5, G1): "South district" = branches A, B and C.

A group names several branches of one business so a screen, a message or an AI agent can be
pointed at all of them at once. A branch may sit in more than one group. A group only holds
branches of its own business (the membership carries the tenant), and deleting a branch or a group
only removes the membership.

Revision ID: 0085
Revises: 0083
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0085"
down_revision: str | None = "0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.location_groups (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
            sort_order  smallint NOT NULL DEFAULT 0,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX location_groups_name ON app.location_groups (tenant_id, lower(name))
    """)
    op.execute("""
        CREATE TABLE app.location_group_members (
            tenant_id   uuid NOT NULL,
            group_id    uuid NOT NULL,
            location_id uuid NOT NULL,
            PRIMARY KEY (tenant_id, group_id, location_id),
            FOREIGN KEY (tenant_id, group_id) REFERENCES app.location_groups (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE INDEX location_group_members_location
            ON app.location_group_members (tenant_id, location_id)
    """)
    for table in ("location_groups", "location_group_members"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    op.execute("DROP TABLE app.location_group_members")
    op.execute("DROP TABLE app.location_groups")
