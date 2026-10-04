"""Clients: where they came from (lead source), for marketing questions.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = ("walk_in", "referral", "instagram", "facebook", "google", "website", "app", "other")

JOIN_WITH_SOURCE = """
        CREATE OR REPLACE FUNCTION app.join_business(p_code text) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user app.users%ROWTYPE;
            v_tenant_id uuid;
            v_client_id uuid;
        BEGIN
            SELECT * INTO v_user FROM app.users WHERE id = app.current_user_id();
            IF v_user.id IS NULL THEN
                RAISE EXCEPTION 'no current user' USING ERRCODE = '42501';
            END IF;
            SELECT t.id INTO v_tenant_id FROM app.tenants t
            WHERE t.join_code = upper(trim(p_code));
            IF v_tenant_id IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT c.id INTO v_client_id FROM app.clients c
            WHERE c.tenant_id = v_tenant_id AND c.user_id = v_user.id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            UPDATE app.clients c SET user_id = v_user.id, updated_at = now()
            WHERE c.id = (
                SELECT c2.id FROM app.clients c2
                WHERE c2.tenant_id = v_tenant_id AND c2.user_id IS NULL
                  AND lower(c2.email) = lower(v_user.email)
                LIMIT 1
            )
            RETURNING c.id INTO v_client_id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            INSERT INTO app.clients (tenant_id, user_id, first_name, email, status, source)
            VALUES (v_tenant_id, v_user.id,
                    coalesce(nullif(trim(v_user.full_name), ''), split_part(v_user.email, '@', 1)),
                    v_user.email, 'active', 'app')
            RETURNING id INTO v_client_id;
            RETURN v_client_id;
        END
        $$
"""

JOIN_WITHOUT_SOURCE = """
        CREATE OR REPLACE FUNCTION app.join_business(p_code text) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user app.users%ROWTYPE;
            v_tenant_id uuid;
            v_client_id uuid;
        BEGIN
            SELECT * INTO v_user FROM app.users WHERE id = app.current_user_id();
            IF v_user.id IS NULL THEN
                RAISE EXCEPTION 'no current user' USING ERRCODE = '42501';
            END IF;
            SELECT t.id INTO v_tenant_id FROM app.tenants t
            WHERE t.join_code = upper(trim(p_code));
            IF v_tenant_id IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT c.id INTO v_client_id FROM app.clients c
            WHERE c.tenant_id = v_tenant_id AND c.user_id = v_user.id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            UPDATE app.clients c SET user_id = v_user.id, updated_at = now()
            WHERE c.id = (
                SELECT c2.id FROM app.clients c2
                WHERE c2.tenant_id = v_tenant_id AND c2.user_id IS NULL
                  AND lower(c2.email) = lower(v_user.email)
                LIMIT 1
            )
            RETURNING c.id INTO v_client_id;
            IF v_client_id IS NOT NULL THEN
                RETURN v_client_id;
            END IF;

            INSERT INTO app.clients (tenant_id, user_id, first_name, email, status)
            VALUES (v_tenant_id, v_user.id,
                    coalesce(nullif(trim(v_user.full_name), ''), split_part(v_user.email, '@', 1)),
                    v_user.email, 'active')
            RETURNING id INTO v_client_id;
            RETURN v_client_id;
        END
        $$
"""


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE app.clients ADD COLUMN source text
            CHECK (source IN ({", ".join(f"'{s}'" for s in SOURCES)}))
    """)
    # Clients who join through the app are recorded as coming from the app.
    op.execute(JOIN_WITH_SOURCE)


def downgrade() -> None:
    op.execute(JOIN_WITHOUT_SOURCE)
    op.execute("ALTER TABLE app.clients DROP COLUMN source")
