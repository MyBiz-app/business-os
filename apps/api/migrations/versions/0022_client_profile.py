"""Clients edit their own name and phone in the client app.

Clients share the API's database role with staff, so a row policy can't limit which
columns they change; app.update_my_profile changes exactly these three fields of the
signed-in user's client record in the current business.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION app.update_my_profile(
            p_first_name text, p_last_name text, p_phone text
        ) RETURNS void
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
            UPDATE app.clients
            SET first_name = p_first_name, last_name = p_last_name, phone = p_phone,
                updated_at = now()
            WHERE id = app.current_client_id() AND erased_at IS NULL
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.update_my_profile(text, text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.update_my_profile(text, text, text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.update_my_profile(text, text, text)")
