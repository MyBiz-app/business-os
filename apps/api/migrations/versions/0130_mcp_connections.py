"""AI connectors: Claude and ChatGPT reading a business through MCP (round 7, R37a).

Expand step only: two new tables and three functions.

* `app.mcp_clients`: the apps that registered themselves to ask for access (OAuth dynamic client
  registration: a name and the redirect addresses). Shared by every business, so the API only
  reads and adds rows.
* `app.mcp_connections`: one row per person who let an AI app into one business. It keeps only
  hashes (of the one-time code, the access token and the refresh token), never a token itself.
  Revoking a connection (`revoked_at`) cuts it off at once.
* `app.mcp_exchange_code`, `app.mcp_refresh` and `app.mcp_authenticate`: the token endpoint and
  the MCP endpoint know no business yet when they receive a code or a token, so these look the
  connection up by hash. They are the only way in; the PKCE check runs inside the exchange so a
  code can be used once, by the app that asked, and only with the secret it started with.

# contract: only the downgrade drops anything (the two tables and the functions); the upgrade
# adds them and touches nothing that exists, so the previous API version keeps working.

Revision ID: 0130
Revises: 0129
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0130"
down_revision: str | None = "0129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "mcp_exchange_code(text, text, text, text, text, timestamptz, text, timestamptz)",
    "mcp_refresh(text, text, text, timestamptz, text, timestamptz)",
    "mcp_authenticate(text)",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.mcp_clients (
            client_id     text PRIMARY KEY,
            client_name   text NOT NULL CHECK (length(client_name) BETWEEN 1 AND 100),
            redirect_uris text[] NOT NULL CHECK (cardinality(redirect_uris) BETWEEN 1 AND 5),
            created_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE app.mcp_connections (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id          uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id            uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
            client_id          text NOT NULL REFERENCES app.mcp_clients (client_id),
            client_name        text NOT NULL,
            scopes             text[] NOT NULL DEFAULT '{read}',
            redirect_uri       text,
            code_hash          text UNIQUE,
            code_challenge     text,
            code_expires_at    timestamptz,
            access_hash        text UNIQUE,
            access_expires_at  timestamptz,
            refresh_hash       text UNIQUE,
            refresh_expires_at timestamptz,
            calls              bigint NOT NULL DEFAULT 0,
            created_at         timestamptz NOT NULL DEFAULT now(),
            last_used_at       timestamptz,
            revoked_at         timestamptz
        )
    """)
    op.execute(
        "CREATE INDEX mcp_connections_tenant_idx ON app.mcp_connections (tenant_id, user_id)"
    )
    op.execute("CREATE INDEX mcp_connections_user_idx ON app.mcp_connections (user_id)")
    op.execute("CREATE INDEX mcp_connections_client_idx ON app.mcp_connections (client_id)")
    for table in ("mcp_clients", "mcp_connections"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON app.mcp_clients TO app_api")
    op.execute("""
        CREATE POLICY mcp_clients_read ON app.mcp_clients FOR SELECT TO app_api USING (true)
    """)
    op.execute("""
        CREATE POLICY mcp_clients_register ON app.mcp_clients FOR INSERT TO app_api
        WITH CHECK (true)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.mcp_connections TO app_api")
    op.execute("""
        CREATE POLICY mcp_connections_tenant ON app.mcp_connections TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    # A one-time code becomes a pair of tokens. The code is cleared in the same statement, so a
    # second try finds nothing; PKCE (S256) is checked here, against the challenge saved when the
    # person approved.
    op.execute("""
        CREATE FUNCTION app.mcp_exchange_code(
            p_code_hash text, p_client_id text, p_redirect_uri text, p_verifier text,
            p_access_hash text, p_access_expires timestamptz,
            p_refresh_hash text, p_refresh_expires timestamptz
        ) RETURNS uuid
        LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            UPDATE app.mcp_connections c SET
                code_hash = NULL, code_challenge = NULL, code_expires_at = NULL,
                redirect_uri = NULL,
                access_hash = p_access_hash, access_expires_at = p_access_expires,
                refresh_hash = p_refresh_hash, refresh_expires_at = p_refresh_expires
            WHERE c.code_hash = p_code_hash AND c.code_expires_at > now()
              AND c.revoked_at IS NULL AND c.client_id = p_client_id
              AND c.redirect_uri = p_redirect_uri
              AND c.code_challenge = rtrim(translate(
                    encode(sha256(convert_to(p_verifier, 'UTF8')), 'base64'), '+/', '-_'), '=')
            RETURNING c.id
        $$
    """)
    # A refresh token is used once and replaced by a new pair.
    op.execute("""
        CREATE FUNCTION app.mcp_refresh(
            p_refresh_hash text, p_client_id text,
            p_access_hash text, p_access_expires timestamptz,
            p_new_refresh_hash text, p_refresh_expires timestamptz
        ) RETURNS uuid
        LANGUAGE sql SECURITY DEFINER SET search_path = ''
        AS $$
            UPDATE app.mcp_connections c SET
                access_hash = p_access_hash, access_expires_at = p_access_expires,
                refresh_hash = p_new_refresh_hash, refresh_expires_at = p_refresh_expires
            WHERE c.refresh_hash = p_refresh_hash AND c.refresh_expires_at > now()
              AND c.revoked_at IS NULL AND c.client_id = p_client_id
            RETURNING c.id
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.mcp_authenticate(p_access_hash text)
        RETURNS TABLE (id uuid, tenant_id uuid, user_id uuid, client_name text, scopes text[])
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT c.id, c.tenant_id, c.user_id, c.client_name, c.scopes
            FROM app.mcp_connections c
            WHERE c.access_hash = p_access_hash AND c.access_expires_at > now()
              AND c.revoked_at IS NULL
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    # contract: only a rollback of this release drops the tables and functions, and nothing
    # else reads them
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.mcp_connections, app.mcp_clients")
