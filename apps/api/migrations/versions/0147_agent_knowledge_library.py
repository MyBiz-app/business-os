"""A knowledge library for each console AI agent (slice C3a).

Each agent of MyBiz's team can have its own library: files, links, notes of the team and an
approved summary. A document keeps every version of its text; the text is cut into chunks that the
agent searches (full text search, works in Hebrew and English). Search by meaning (pgvector) is
built but off: the `vector` extension is created when the database offers it (Supabase does, for
free) and the chunks get an `embedding` column; nothing is embedded until the embeddings provider
is switched on (docs/deploy/go-live-checklist.md).

Like the other console AI settings the tables are not reachable from the API role: only SECURITY
DEFINER functions touch them. Reading needs the console team, changing needs `billing.manage`, and
every change is written to the console audit log.

Revision ID: 0147
Revises: 0146
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0147"
down_revision: str | None = "0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = (
    "manager",
    "support",
    "health",
    "billing",
    "growth",
    "legal",
    "accountant",
    "market",
    "security",
    "product",
    "success",
    "marketing",
)
KINDS = ("file", "link", "note", "summary")
FUNCTIONS = (
    "platform_kb_documents(text)",
    "platform_kb_document(uuid)",
    "platform_kb_versions(uuid)",
    "platform_kb_version_body(uuid, integer)",
    "platform_kb_save(uuid, text, text, text, text, text, text, date, boolean, text, text, jsonb)",
    "platform_kb_set_enabled(uuid, boolean)",
    "platform_kb_delete(uuid)",
    "platform_kb_search(text, text, integer)",
    "platform_kb_always(text)",
    "platform_kb_vector_ready()",
    "platform_kb_pending_embeddings(integer)",
    "platform_kb_set_embeddings(uuid, jsonb)",
    "platform_kb_vector_search(text, text, integer)",
)


# The libraries start with links to official public sources, each for the agent that needs it.
# The console reads their text (Library > "Read the sources"); the team can change, switch off or
# delete any of them. (agent, kind, title, url, organisation, country)
SOURCES = (
    (
        "legal",
        "link",
        "Privacy Protection Authority (Israel)",
        "https://www.gov.il/en/departments/the_privacy_protection_authority/govil-landing-page",
        "Privacy Protection Authority",
        "il",
    ),
    (
        "legal",
        "link",
        "Consumer Protection and Fair Trade Authority (Israel)",
        "https://www.gov.il/he/departments/the_consumer_protection_and_fair_trade_authority/govil-landing-page",
        "Consumer Protection and Fair Trade Authority",
        "il",
    ),
    (
        "legal",
        "link",
        "Commission for Equal Rights of Persons with Disabilities (Israel)",
        "https://www.gov.il/he/departments/the_commission_for_equal_rights_of_persons_with_disabilities/govil-landing-page",
        "Commission for Equal Rights of Persons with Disabilities",
        "il",
    ),
    (
        "legal",
        "link",
        "CCPA, California privacy law",
        "https://oag.ca.gov/privacy/ccpa",
        "California Attorney General",
        "us",
    ),
    (
        "legal",
        "link",
        "CAN-SPAM Act, compliance guide for business",
        "https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business",
        "Federal Trade Commission",
        "us",
    ),
    (
        "legal",
        "link",
        "TCPA, telemarketing and robocalls (calls and texts)",
        "https://www.fcc.gov/general/telemarketing-and-robocalls",
        "Federal Communications Commission",
        "us",
    ),
    (
        "legal",
        "link",
        "ADA, web accessibility guidance",
        "https://www.ada.gov/resources/web-guidance/",
        "US Department of Justice",
        "us",
    ),
    (
        "legal",
        "link",
        "FTC advertising and marketing guidance for business",
        "https://www.ftc.gov/business-guidance/advertising-marketing",
        "Federal Trade Commission",
        "us",
    ),
    (
        "legal",
        "link",
        "GDPR, Regulation (EU) 2016/679",
        "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "EUR-Lex",
        "eu",
    ),
    (
        "legal",
        "link",
        "ePrivacy Directive 2002/58/EC",
        "https://eur-lex.europa.eu/eli/dir/2002/58/oj",
        "EUR-Lex",
        "eu",
    ),
    (
        "accountant",
        "link",
        "Israel Tax Authority",
        "https://www.gov.il/he/departments/israel_tax_authority/govil-landing-page",
        "Israel Tax Authority",
        "il",
    ),
    (
        "accountant",
        "link",
        "IRS small business and self-employed",
        "https://www.irs.gov/businesses/small-businesses-self-employed",
        "IRS",
        "us",
    ),
    (
        "accountant",
        "link",
        "IRS Publication 334, tax guide for small business",
        "https://www.irs.gov/publications/p334",
        "IRS",
        "us",
    ),
    (
        "accountant",
        "link",
        "IRS Publication 15, employer's tax guide",
        "https://www.irs.gov/publications/p15",
        "IRS",
        "us",
    ),
    (
        "accountant",
        "link",
        "IRS Publication 535, business expenses",
        "https://www.irs.gov/publications/p535",
        "IRS",
        "us",
    ),
    ("security", "link", "OWASP Top Ten", "https://owasp.org/www-project-top-ten/", "OWASP", "all"),
    (
        "security",
        "link",
        "OWASP Application Security Verification Standard",
        "https://owasp.org/www-project-application-security-verification-standard/",
        "OWASP",
        "all",
    ),
    (
        "security",
        "link",
        "OWASP Cheat Sheet Series",
        "https://cheatsheetseries.owasp.org/",
        "OWASP",
        "all",
    ),
    (
        "security",
        "link",
        "NIST Cybersecurity Framework",
        "https://www.nist.gov/cyberframework",
        "NIST",
        "us",
    ),
    (
        "security",
        "link",
        "CISA Known Exploited Vulnerabilities catalog",
        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "CISA",
        "us",
    ),
    (
        "security",
        "link",
        "Israel National Cyber Directorate",
        "https://www.gov.il/he/departments/israel_national_cyber_directorate/govil-landing-page",
        "Israel National Cyber Directorate",
        "il",
    ),
    (
        "marketing",
        "link",
        "Google Search Central, SEO starter guide",
        "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
        "Google",
        "all",
    ),
    (
        "marketing",
        "link",
        "FTC advertising and marketing guidance for business",
        "https://www.ftc.gov/business-guidance/advertising-marketing",
        "Federal Trade Commission",
        "us",
    ),
)


def _list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What the search functions return, the same for the words search and the meaning search.
HIT = """
    document_id uuid, agent_key text, title text, source_url text, source_org text,
    country text, reviewed_on date, heading text, content text, rank double precision
"""


def seed_sources(connection: sa.Connection) -> None:
    """Adds the official sources (separate so a test can load them after it empties the tables)."""
    for agent, kind, title, url, org, country in SOURCES:
        document = connection.execute(
            sa.text("""
                INSERT INTO app.platform_kb_documents
                    (agent_key, kind, title, source_url, source_org, country,
                     created_by, updated_by)
                VALUES (:agent, :kind, :title, :url, :org, :country, 'seed', 'seed')
                RETURNING id
            """),
            {
                "agent": agent,
                "kind": kind,
                "title": title,
                "url": url,
                "org": org,
                "country": country,
            },
        ).scalar_one()
        connection.execute(
            sa.text("""
                INSERT INTO app.platform_kb_versions (document_id, version, change_note, created_by)
                VALUES (:id, 1, 'Official source added with the library', 'seed')
            """),
            {"id": document},
        )


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    # pgvector, when the database has it. Plain PostgreSQL (the test database) does not; the
    # library then works with full text search only.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                NULL;
            ELSIF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
                CREATE EXTENSION vector WITH SCHEMA extensions;
            ELSE
                RAISE NOTICE 'pgvector is not available: the library searches by words only';
            END IF;
        END $$
    """)

    op.execute(f"""
        CREATE TABLE app.platform_kb_documents (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_key   text NOT NULL CHECK (agent_key IN ({_list(ROLES)})),
            kind        text NOT NULL CHECK (kind IN ({_list(KINDS)})),
            title       text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            source_url  text CHECK (source_url ~ '^https?://' AND length(source_url) <= 1000),
            source_org  text CHECK (length(source_org) <= 200),
            country     text CHECK (country IN ('il', 'us', 'eu', 'all')),
            reviewed_on date,
            enabled     boolean NOT NULL DEFAULT true,
            version     integer NOT NULL DEFAULT 1,
            created_by  text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_by  text NOT NULL,
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX platform_kb_documents_agent_idx "
        "ON app.platform_kb_documents (agent_key, kind, title)"
    )
    op.execute("""
        CREATE TABLE app.platform_kb_versions (
            document_id uuid NOT NULL
                        REFERENCES app.platform_kb_documents (id) ON DELETE CASCADE,
            version     integer NOT NULL,
            body        text CHECK (length(body) <= 400000),
            change_note text CHECK (length(change_note) <= 300),
            created_by  text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (document_id, version)
        )
    """)
    op.execute("""
        CREATE TABLE app.platform_kb_chunks (
            document_id uuid NOT NULL
                        REFERENCES app.platform_kb_documents (id) ON DELETE CASCADE,
            ordinal     integer NOT NULL,
            heading     text,
            content     text NOT NULL,
            tsv         tsvector GENERATED ALWAYS AS
                        (to_tsvector('simple', coalesce(heading, '') || ' ' || content)) STORED,
            PRIMARY KEY (document_id, ordinal)
        )
    """)
    op.execute("CREATE INDEX platform_kb_chunks_tsv_idx ON app.platform_kb_chunks USING gin (tsv)")
    op.execute("""
        DO $$
        BEGIN
            IF to_regtype('extensions.vector') IS NOT NULL THEN
                ALTER TABLE app.platform_kb_chunks ADD COLUMN embedding extensions.vector(1024);
                CREATE INDEX platform_kb_chunks_embedding_idx
                    ON app.platform_kb_chunks USING hnsw (embedding extensions.vector_cosine_ops);
            END IF;
        END $$
    """)
    for table in ("documents", "versions", "chunks"):
        op.execute(f"ALTER TABLE app.platform_kb_{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON app.platform_kb_{table} FROM app_api")

    op.execute("""
        CREATE FUNCTION app.platform_kb_documents(p_agent text)
        RETURNS TABLE (id uuid, agent_key text, kind text, title text, source_url text,
                       source_org text, country text, reviewed_on date, enabled boolean,
                       version integer, chars integer, chunks integer, updated_by text,
                       updated_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT d.id, d.agent_key, d.kind, d.title, d.source_url, d.source_org, d.country,
                   d.reviewed_on, d.enabled, d.version,
                   coalesce(length(v.body), 0)::integer,
                   (SELECT count(*)::integer FROM app.platform_kb_chunks c
                    WHERE c.document_id = d.id),
                   d.updated_by, d.updated_at
            FROM app.platform_kb_documents d
            LEFT JOIN app.platform_kb_versions v
                   ON v.document_id = d.id AND v.version = d.version
            WHERE d.agent_key = p_agent
            ORDER BY d.kind, d.title
            LIMIT 300;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_document(p_id uuid)
        RETURNS TABLE (id uuid, agent_key text, kind text, title text, source_url text,
                       source_org text, country text, reviewed_on date, enabled boolean,
                       version integer, body text, updated_by text, updated_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT d.id, d.agent_key, d.kind, d.title, d.source_url, d.source_org, d.country,
                   d.reviewed_on, d.enabled, d.version, v.body, d.updated_by, d.updated_at
            FROM app.platform_kb_documents d
            LEFT JOIN app.platform_kb_versions v
                   ON v.document_id = d.id AND v.version = d.version
            WHERE d.id = p_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_versions(p_id uuid)
        RETURNS TABLE (version integer, change_note text, created_by text,
                       created_at timestamptz, chars integer)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT v.version, v.change_note, v.created_by, v.created_at,
                   coalesce(length(v.body), 0)::integer
            FROM app.platform_kb_versions v
            WHERE v.document_id = p_id
            ORDER BY v.version DESC
            LIMIT 100;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_version_body(p_id uuid, p_version integer)
        RETURNS text
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN (SELECT v.body FROM app.platform_kb_versions v
                    WHERE v.document_id = p_id AND v.version = p_version);
        END
        $$
    """)
    # Creates a document (p_id null) or changes one. A new text is a new version; the chunks of
    # the new text come from the caller (p_chunks: [{"heading": ..., "content": ...}]).
    op.execute("""
        CREATE FUNCTION app.platform_kb_save(
            p_id uuid, p_agent text, p_kind text, p_title text, p_url text, p_org text,
            p_country text, p_reviewed date, p_enabled boolean, p_body text, p_note text,
            p_chunks jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
            v_id uuid := p_id;
            v_version integer;
            v_old text;
            v_body text := nullif(p_body, '');
            v_changed boolean := true;
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF v_id IS NULL THEN
                INSERT INTO app.platform_kb_documents
                    (agent_key, kind, title, source_url, source_org, country, reviewed_on,
                     enabled, created_by, updated_by)
                VALUES (p_agent, p_kind, trim(p_title), nullif(trim(p_url), ''),
                        nullif(trim(p_org), ''), nullif(p_country, ''), p_reviewed, p_enabled,
                        v_email, v_email)
                RETURNING id, version INTO v_id, v_version;
                INSERT INTO app.platform_kb_versions (document_id, version, body, change_note,
                                                      created_by)
                VALUES (v_id, v_version, v_body, nullif(trim(p_note), ''), v_email);
            ELSE
                SELECT d.version, v.body INTO v_version, v_old
                FROM app.platform_kb_documents d
                JOIN app.platform_kb_versions v
                  ON v.document_id = d.id AND v.version = d.version
                WHERE d.id = v_id FOR UPDATE OF d;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
                END IF;
                v_changed := v_body IS DISTINCT FROM v_old;
                IF v_changed THEN
                    v_version := v_version + 1;
                    INSERT INTO app.platform_kb_versions (document_id, version, body,
                                                          change_note, created_by)
                    VALUES (v_id, v_version, v_body, nullif(trim(p_note), ''), v_email);
                END IF;
                UPDATE app.platform_kb_documents
                SET title = trim(p_title), source_url = nullif(trim(p_url), ''),
                    source_org = nullif(trim(p_org), ''), country = nullif(p_country, ''),
                    reviewed_on = p_reviewed, enabled = p_enabled, version = v_version,
                    updated_by = v_email, updated_at = now()
                WHERE id = v_id;
            END IF;
            IF v_changed THEN
                DELETE FROM app.platform_kb_chunks WHERE document_id = v_id;
                INSERT INTO app.platform_kb_chunks (document_id, ordinal, heading, content)
                SELECT v_id, (c.ordinality - 1)::integer, nullif(c.value ->> 'heading', ''),
                       c.value ->> 'content'
                FROM jsonb_array_elements(coalesce(p_chunks, '[]'::jsonb))
                     WITH ORDINALITY AS c(value, ordinality);
            END IF;
            PERFORM app.platform_audit_add(
                'ai.library', NULL,
                jsonb_build_object('agent', p_agent, 'document', v_id, 'title', trim(p_title),
                                   'kind', p_kind, 'version', v_version,
                                   'created', p_id IS NULL, 'enabled', p_enabled));
            RETURN v_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_set_enabled(p_id uuid, p_enabled boolean)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_email text := (SELECT email FROM app.platform_me());
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.platform_kb_documents
            SET enabled = p_enabled, updated_by = v_email, updated_at = now()
            WHERE id = p_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            PERFORM app.platform_audit_add(
                'ai.library', NULL,
                jsonb_build_object('document', p_id, 'enabled', p_enabled));
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_delete(p_id uuid)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_title text;
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            DELETE FROM app.platform_kb_documents WHERE id = p_id RETURNING title INTO v_title;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            PERFORM app.platform_audit_add(
                'ai.library', NULL,
                jsonb_build_object('document', p_id, 'title', v_title, 'deleted', true));
        END
        $$
    """)
    # Search by words. p_query is a to_tsquery text built by the caller from the question; the
    # agent is null for the chief, who reads every library.
    op.execute(f"""
        CREATE FUNCTION app.platform_kb_search(p_agent text, p_query text, p_limit integer)
        RETURNS TABLE ({HIT})
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT d.id, d.agent_key, d.title, d.source_url, d.source_org, d.country,
                   d.reviewed_on, c.heading, c.content,
                   ts_rank_cd(c.tsv, q.query)::double precision
            FROM app.platform_kb_chunks c
            JOIN app.platform_kb_documents d ON d.id = c.document_id
            CROSS JOIN to_tsquery('simple', p_query) AS q(query)
            WHERE d.enabled AND c.tsv @@ q.query
              AND (p_agent IS NULL OR d.agent_key = p_agent)
            ORDER BY 10 DESC, d.title, c.ordinal
            LIMIT least(greatest(p_limit, 1), 20);
        END
        $$
    """)
    # The notes and summaries an agent always gets in its prompt.
    op.execute("""
        CREATE FUNCTION app.platform_kb_always(p_agent text)
        RETURNS TABLE (kind text, title text, body text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT d.kind, d.title, v.body
            FROM app.platform_kb_documents d
            JOIN app.platform_kb_versions v ON v.document_id = d.id AND v.version = d.version
            WHERE d.agent_key = p_agent AND d.enabled AND d.kind IN ('note', 'summary')
              AND v.body IS NOT NULL
            ORDER BY d.kind DESC, d.title
            LIMIT 30;
        END
        $$
    """)
    # --- Search by meaning: built, off until the embeddings provider is switched on ----------
    op.execute("""
        CREATE FUNCTION app.platform_kb_vector_ready()
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT to_regtype('extensions.vector') IS NOT NULL AND EXISTS (
                SELECT 1 FROM pg_attribute a
                WHERE a.attrelid = 'app.platform_kb_chunks'::regclass
                  AND a.attname = 'embedding' AND NOT a.attisdropped)
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.platform_kb_pending_embeddings(p_limit integer)
        RETURNS TABLE (document_id uuid, ordinal integer, content text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT app.platform_kb_vector_ready() THEN
                RETURN;
            END IF;
            RETURN QUERY EXECUTE
                'SELECT c.document_id, c.ordinal, c.content FROM app.platform_kb_chunks c '
                'WHERE c.embedding IS NULL ORDER BY c.document_id, c.ordinal LIMIT '
                || least(greatest(p_limit, 1), 200);
        END
        $$
    """)
    # p_vectors: [{"ordinal": 0, "vector": "[0.1, ...]"}, ...] for the chunks of one document.
    op.execute("""
        CREATE FUNCTION app.platform_kb_set_embeddings(p_document uuid, p_vectors jsonb)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_item jsonb;
        BEGIN
            IF NOT app.platform_can('billing.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT app.platform_kb_vector_ready() THEN
                RETURN;
            END IF;
            FOR v_item IN SELECT * FROM jsonb_array_elements(p_vectors) LOOP
                EXECUTE 'UPDATE app.platform_kb_chunks SET embedding = $1::extensions.vector '
                        'WHERE document_id = $2 AND ordinal = $3'
                USING v_item ->> 'vector', p_document, (v_item ->> 'ordinal')::integer;
            END LOOP;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_kb_vector_search(p_agent text, p_vector text, p_limit integer)
        RETURNS TABLE ({HIT})
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            IF NOT app.platform_kb_vector_ready() THEN
                RETURN;
            END IF;
            RETURN QUERY EXECUTE
                'SELECT d.id, d.agent_key, d.title, d.source_url, d.source_org, d.country, '
                'd.reviewed_on, c.heading, c.content, '
                '(1 - (c.embedding OPERATOR(extensions.<=>) $1::extensions.vector))'
                '::double precision '
                'FROM app.platform_kb_chunks c JOIN app.platform_kb_documents d '
                'ON d.id = c.document_id '
                'WHERE d.enabled AND c.embedding IS NOT NULL AND ($2::text IS NULL '
                'OR d.agent_key = $2) '
                'ORDER BY c.embedding OPERATOR(extensions.<=>) $1::extensions.vector LIMIT $3'
                USING p_vector, p_agent, least(greatest(p_limit, 1), 20);
        END
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")

    seed_sources(op.get_bind())


def downgrade() -> None:
    # contract: only a rollback drops the library; the previous release never reads these tables
    # and functions. The vector extension stays (it may serve other features).
    for function in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION app.{function}")
    for table in ("chunks", "versions", "documents"):
        op.execute(f"DROP TABLE app.platform_kb_{table}")
