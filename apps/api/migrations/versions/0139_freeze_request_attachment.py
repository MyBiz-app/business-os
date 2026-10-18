"""A paper attached to a freeze request (round 7, R23 leftovers).

Expand step. A client can attach a medical note or a call-up paper to a freeze request. The file
itself lives in Files (`client_documents`, uploaded by the client); the request only points at it.
Deleting the document leaves the request in place.

Nothing existing changes: the column is optional and the previous release never selects it.

Revision ID: 0139
Revises: 0138
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0139"
down_revision: str | None = "0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.freeze_requests
            ADD COLUMN document_id uuid REFERENCES app.client_documents (id) ON DELETE SET NULL
    """)
    op.execute(
        "CREATE INDEX freeze_requests_document_idx ON app.freeze_requests (document_id)"
        " WHERE document_id IS NOT NULL"
    )


def downgrade() -> None:
    # contract: a rollback of this release drops the column; nothing else reads it
    op.execute("DROP INDEX app.freeze_requests_document_idx")
    op.execute("ALTER TABLE app.freeze_requests DROP COLUMN document_id")
