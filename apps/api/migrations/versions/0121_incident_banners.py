"""Incident banners (go-live, GL23).

The MyBiz team opens a banner (an incident, planned maintenance or a security event) with a text in
Hebrew and English; every page of the web app and the mobile app shows it until the team resolves
it. It is MyBiz's own table (no tenant, no API access, RLS with no policy): the console writes
through SECURITY DEFINER functions that need the broadcasts permission, and everybody (also before
sign-in) reads the open ones through `app.active_incidents()`, which holds no personal data.

# contract: the only DROP is in downgrade() and removes the table and functions this migration
# added; no earlier API version reads them, so a rollback of the code never touches them.

Revision ID: 0121
Revises: 0120
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0121"
down_revision: str | None = "0120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.platform_incidents (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            kind        text NOT NULL CHECK (kind IN ('incident', 'maintenance', 'security')),
            content     jsonb NOT NULL DEFAULT '{}',
            status_url  text NOT NULL DEFAULT '',
            created_by  text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz,
            resolved_by text
        )
    """)
    op.execute("ALTER TABLE app.platform_incidents ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON app.platform_incidents FROM PUBLIC")
    op.execute(
        "CREATE INDEX platform_incidents_open ON app.platform_incidents (created_at DESC) "
        "WHERE resolved_at IS NULL"
    )

    op.execute("""
        CREATE FUNCTION app.incident_open(p_kind text, p_content jsonb, p_status_url text)
        RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.platform_incidents (kind, content, status_url, created_by)
            VALUES (p_kind, p_content, p_status_url, (SELECT m.email FROM app.platform_me() m))
            RETURNING platform_incidents.id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.incident_resolve(p_id uuid) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            UPDATE app.platform_incidents i
            SET resolved_at = now(), resolved_by = (SELECT m.email FROM app.platform_me() m)
            WHERE i.id = p_id AND i.resolved_at IS NULL
            RETURNING i.id INTO v_id;
            IF v_id IS NULL THEN
                RAISE EXCEPTION 'not_found' USING ERRCODE = 'P0002';
            END IF;
            RETURN v_id;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.incident_rows()
        RETURNS TABLE (id uuid, kind text, content jsonb, status_url text, created_by text,
                       created_at timestamptz, resolved_at timestamptz, resolved_by text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NOT app.platform_can('broadcasts.manage') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT i.id, i.kind, i.content, i.status_url, i.created_by, i.created_at,
                   i.resolved_at, i.resolved_by
            FROM app.platform_incidents i
            ORDER BY i.created_at DESC LIMIT 50;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.active_incidents()
        RETURNS TABLE (id uuid, kind text, content jsonb, status_url text, created_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT i.id, i.kind, i.content, i.status_url, i.created_at
            FROM app.platform_incidents i
            WHERE i.resolved_at IS NULL
            ORDER BY i.created_at DESC LIMIT 5
        $$
    """)
    for function in (
        "incident_open(text, jsonb, text)",
        "incident_resolve(uuid)",
        "incident_rows()",
        "active_incidents()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{function} TO app_api")


def downgrade() -> None:
    for function in (
        "active_incidents()",
        "incident_rows()",
        "incident_resolve(uuid)",
        "incident_open(text, jsonb, text)",
    ):
        op.execute(f"DROP FUNCTION app.{function}")
    op.execute("DROP TABLE app.platform_incidents")
