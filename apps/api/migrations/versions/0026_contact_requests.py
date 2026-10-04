"""Contact requests from the marketing site: businesses interested in MyBiz.

A platform table (no tenant). The API never touches it directly: anyone may submit through
app.submit_contact_request (validated, rate limited per email), and only platform admins read
it through app.platform_contact_requests.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.contact_requests (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name        text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
            email       text NOT NULL CHECK (length(email) BETWEEN 3 AND 254),
            phone       text CHECK (length(phone) <= 40),
            business    text CHECK (length(business) <= 160),
            vertical    text CHECK (vertical IN ('fitness', 'beauty', 'clinic', 'garage', 'other')),
            message     text CHECK (length(message) <= 4000),
            locale      text NOT NULL CHECK (locale IN ('he', 'en')),
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX contact_requests_email ON app.contact_requests (email, created_at)")
    op.execute("ALTER TABLE app.contact_requests ENABLE ROW LEVEL SECURITY")  # no API access

    op.execute("""
        CREATE FUNCTION app.submit_contact_request(
            p_name text, p_email text, p_phone text, p_business text, p_vertical text,
            p_message text, p_locale text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_id uuid;
        BEGIN
            -- At most 3 requests per email address an hour.
            IF (SELECT count(*) FROM app.contact_requests
                WHERE lower(email) = lower(p_email)
                  AND created_at > now() - interval '1 hour') >= 3 THEN
                RAISE EXCEPTION 'too many requests' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.contact_requests
                (name, email, phone, business, vertical, message, locale)
            VALUES (p_name, lower(p_email), p_phone, p_business, p_vertical, p_message, p_locale)
            RETURNING id INTO v_id;
            RETURN v_id;
        END
        $$
    """)
    signature = "app.submit_contact_request(text, text, text, text, text, text, text)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")

    op.execute("""
        CREATE FUNCTION app.platform_contact_requests()
        RETURNS TABLE (id uuid, name text, email text, phone text, business text, vertical text,
                       message text, locale text, created_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF NOT app.is_platform_admin() THEN
                RAISE EXCEPTION 'platform admins only' USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT r.id, r.name, r.email, r.phone, r.business, r.vertical, r.message, r.locale,
                   r.created_at
            FROM app.contact_requests r ORDER BY r.created_at DESC LIMIT 200;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.platform_contact_requests() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.platform_contact_requests() TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.platform_contact_requests()")
    op.execute("DROP FUNCTION app.submit_contact_request(text, text, text, text, text, text, text)")
    op.execute("DROP TABLE app.contact_requests")
