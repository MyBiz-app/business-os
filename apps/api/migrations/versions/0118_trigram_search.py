"""Fast search for clients and leads (go-live, GL17).

Searching for a client or a lead matches the typed text anywhere in the name, email or phone
(`ILIKE '%x%'`), which reads every row without an index. A trigram index (`pg_trgm`) answers it
from the index, also at tens of thousands of clients per business.

The extensions live in the `extensions` schema, not in `public` (a Supabase advisor warning), so
`btree_gist` (created in `public` by 0044) moves there too. Constraints that use it keep working:
they reference the operators by identity, not by name.

Row level security stops Postgres from using the index in a plain query: `ILIKE` is not
"leakproof", so it may not run before the policy. The search therefore goes through two
SECURITY DEFINER functions that return the ids of the current business's matches (always
filtered by `app.current_tenant_id()`); the list queries then keep their own branch filters on
those ids. The expressions inside the functions must match the indexes word for word.

# contract: ALTER EXTENSION btree_gist SET SCHEMA moves only the extension's own objects; the
# exclusion constraints on rooms/resources bind to the operators by OID, so the previous API
# version keeps working on this database.

Revision ID: 0118
Revises: 0117
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0118"
down_revision: str | None = "0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLIENT_TEXT = (
    "(coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' || "
    "coalesce(email, '') || ' ' || coalesce(phone, ''))"
)
LEAD_TEXT = (
    "(coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' || "
    "coalesce(email, '') || ' ' || coalesce(phone, '') || ' ' || coalesce(interest, ''))"
)


def _into_extensions(extension: str) -> str:
    return f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = '{extension}') THEN
                ALTER EXTENSION {extension} SET SCHEMA extensions;
            ELSE
                CREATE EXTENSION {extension} WITH SCHEMA extensions;
            END IF;
        END $$
    """


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute(_into_extensions("btree_gist"))
    op.execute(_into_extensions("pg_trgm"))
    op.execute(
        f"CREATE INDEX clients_search_trgm_idx ON app.clients "
        f"USING gin ({CLIENT_TEXT} extensions.gin_trgm_ops)"
    )
    op.execute(
        f"CREATE INDEX leads_search_trgm_idx ON app.leads "
        f"USING gin ({LEAD_TEXT} extensions.gin_trgm_ops)"
    )

    for name, table, text in (
        ("search_client_ids", "clients", CLIENT_TEXT),
        ("search_lead_ids", "leads", LEAD_TEXT),
    ):
        op.execute(f"""
            CREATE FUNCTION app.{name}(p_pattern text) RETURNS SETOF uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' ROWS 200
            AS $$
                SELECT id FROM app.{table}
                WHERE tenant_id = app.current_tenant_id() AND {text} ILIKE p_pattern
            $$
        """)
        op.execute(f"REVOKE ALL ON FUNCTION app.{name}(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{name}(text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.search_lead_ids(text)")
    op.execute("DROP FUNCTION IF EXISTS app.search_client_ids(text)")
    op.execute("DROP INDEX IF EXISTS app.leads_search_trgm_idx")
    op.execute("DROP INDEX IF EXISTS app.clients_search_trgm_idx")
