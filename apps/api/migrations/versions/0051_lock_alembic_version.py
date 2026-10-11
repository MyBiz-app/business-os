"""Lock Alembic's bookkeeping table away from Supabase's public roles.

`public.alembic_version` is created by Alembic in the `public` schema, which Supabase exposes
through its Data API. Supabase grants `anon` and `authenticated` every privilege on new public
tables, so anyone holding the public (anon) key could read, rewrite or empty it and break the
next migration run. Row-level security with no policy plus revoked grants closes that; Alembic
itself runs as the table owner and is unaffected.

Revision ID: 0051
Revises: 0050
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON public.alembic_version FROM PUBLIC")
    # The roles exist on Supabase only (not in a plain Postgres, as in CI).
    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
          FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
              EXECUTE format('REVOKE ALL ON public.alembic_version FROM %I', role_name);
            END IF;
          END LOOP;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY")
