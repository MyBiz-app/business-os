"""A country for every business, and the first guides of the legal and accountant agents (C3b).

`app.tenants.country` is an ISO 3166 code in capitals (IL, US). Existing businesses get it from
their currency (ILS: IL, USD: US); a business with another currency stays empty, and the agents then
say the country is not set. A trigger fills it for every new business the same way, so no signup
path has to know about it.

The legal and accountant agents start with four draft guides (legal and tax, Israel and the United
States) in their libraries, written from the public official sources the library already links.
They are marked as not reviewed: the team's lawyer and accountant approve them first.

Revision ID: 0149
Revises: 0148
Create Date: 2026-10-19
"""

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0149"
down_revision: str | None = "0148"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUIDES = Path(__file__).parents[2] / "app" / "ai" / "guides"
# (agent, file, title, country, source link, source organisation)
GUIDE_DOCUMENTS = (
    ("legal", "legal-il", "Draft guide: legal, Israel", "il", "Privacy Protection Authority"),
    ("legal", "legal-us", "Draft guide: legal, United States", "us", "FTC, FCC, California AG"),
    ("accountant", "tax-il", "Draft guide: tax, Israel", "il", "Israel Tax Authority"),
    ("accountant", "tax-us", "Draft guide: tax, United States", "us", "IRS"),
)


def sections(body: str) -> list[tuple[str | None, str]]:
    """The text cut at its second level headings, each with its heading."""
    parts: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in body.splitlines():
        if line.startswith("## "):
            parts.append((line[3:].strip(), []))
        else:
            parts[-1][1].append(line)
    return [(h, "\n".join(lines).strip()) for h, lines in parts if "\n".join(lines).strip()]


def seed_guides(connection: sa.Connection) -> None:
    """Adds the guides (separate so a test can load them after it empties the tables)."""
    for agent, name, title, country, org in GUIDE_DOCUMENTS:
        body = (GUIDES / f"{name}.md").read_text(encoding="utf-8")
        document = connection.execute(
            sa.text("""
                INSERT INTO app.platform_kb_documents
                    (agent_key, kind, title, source_org, country, created_by, updated_by)
                VALUES (:agent, 'file', :title, :org, :country, 'seed', 'seed')
                RETURNING id
            """),
            {"agent": agent, "title": title, "org": org, "country": country},
        ).scalar_one()
        connection.execute(
            sa.text("""
                INSERT INTO app.platform_kb_versions
                    (document_id, version, body, change_note, created_by)
                VALUES (:id, 1, :body, 'Draft guide added with the library, not yet reviewed',
                        'seed')
            """),
            {"id": document, "body": body},
        )
        for ordinal, (heading, content) in enumerate(sections(body)):
            connection.execute(
                sa.text("""
                    INSERT INTO app.platform_kb_chunks (document_id, ordinal, heading, content)
                    VALUES (:id, :ordinal, :heading, :content)
                """),
                {"id": document, "ordinal": ordinal, "heading": heading, "content": content},
            )


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN country text CHECK (country ~ '^[A-Z]{2}$')
    """)
    op.execute("""
        CREATE FUNCTION app.country_for_currency(p_currency text) RETURNS text
        LANGUAGE sql IMMUTABLE SET search_path = ''
        AS $$ SELECT CASE p_currency WHEN 'ILS' THEN 'IL' WHEN 'USD' THEN 'US' END $$
    """)
    op.execute("""
        UPDATE app.tenants SET country = app.country_for_currency(currency::text)
        WHERE country IS NULL
    """)
    op.execute("""
        CREATE FUNCTION app.tenants_default_country() RETURNS trigger
        LANGUAGE plpgsql SET search_path = ''
        AS $$
        BEGIN
            NEW.country := coalesce(NEW.country, app.country_for_currency(NEW.currency::text));
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER tenants_default_country BEFORE INSERT ON app.tenants
        FOR EACH ROW EXECUTE FUNCTION app.tenants_default_country()
    """)
    # The console reads a business's country (the API role has no access to the row itself).
    op.execute("""
        CREATE FUNCTION app.platform_business_country(p_id uuid) RETURNS text
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN (SELECT t.country FROM app.tenants t WHERE t.id = p_id);
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_business_country(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_business_country(uuid) TO app_api")
    seed_guides(op.get_bind())


def downgrade() -> None:
    # contract: only a rollback drops the column and the guides; the previous release never reads
    # `country` (it ignores unknown columns) and never reads these guide documents by name.
    op.execute("""
        DELETE FROM app.platform_kb_documents
        WHERE created_by = 'seed' AND title LIKE 'Draft guide: %'
    """)
    op.execute("DROP FUNCTION app.platform_business_country(uuid)")
    op.execute("DROP TRIGGER tenants_default_country ON app.tenants")
    op.execute("DROP FUNCTION app.tenants_default_country()")
    op.execute("DROP FUNCTION app.country_for_currency(text)")
    op.execute("ALTER TABLE app.tenants DROP COLUMN country")
