"""Read-only views for the console's security and legal centers (K4).

Every function checks that the caller is a MyBiz owner and returns a bounded, read-only slice:
the business owners and whether each has two-step sign-in or acknowledged the risk, how often the
MyBiz team entered businesses, who accepted which version of each legal document, and the privacy
requests (exports, erasures, closures) without any client details. No table changes.

Two-step sign-in lives in Supabase's `auth` schema, which a plain Postgres (tests, local) may not
have: there the flag is NULL ("unknown"), never a made-up false.

Revision ID: 0148
Revises: 0147
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0148"
down_revision: str | None = "0147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_GUARD = """
            IF coalesce((SELECT m.level FROM app.platform_me() m), '')
                   NOT IN ('primary_owner', 'owner') THEN
                RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
            END IF;
"""

FUNCTIONS = (
    "platform_security_owners(text)",
    "platform_security_visits(integer)",
    "platform_legal_coverage(jsonb)",
    "platform_legal_acceptances(integer)",
    "platform_privacy_requests()",
)


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION app.platform_security_owners(p_risk_version text)
        RETURNS TABLE (user_id uuid, email text, business_id uuid, business_name text,
                       requires_mfa boolean, mfa_enrolled boolean,
                       risk_acknowledged_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            {OWNER_GUARD}
            IF to_regclass('auth.mfa_factors') IS NOT NULL THEN
                RETURN QUERY EXECUTE $q$
                    SELECT u.id, u.email, t.id, t.name, t.require_mfa_for_staff,
                           EXISTS (SELECT 1 FROM auth.mfa_factors f
                                   WHERE f.user_id = u.id AND f.status = 'verified'),
                           (SELECT max(a.acknowledged_at) FROM app.mfa_risk_acknowledgements a
                            WHERE a.user_id = u.id AND a.version = $1)
                    FROM app.tenant_members m
                    JOIN app.tenants t ON t.id = m.tenant_id AND t.closed_at IS NULL
                    JOIN app.users u ON u.id = m.user_id
                    WHERE m.role = 'owner'
                    ORDER BY t.name, u.email LIMIT 500
                $q$ USING p_risk_version;
            ELSE
                RETURN QUERY
                SELECT u.id, u.email, t.id, t.name, t.require_mfa_for_staff, NULL::boolean,
                       (SELECT max(a.acknowledged_at) FROM app.mfa_risk_acknowledgements a
                        WHERE a.user_id = u.id AND a.version = p_risk_version)
                FROM app.tenant_members m
                JOIN app.tenants t ON t.id = m.tenant_id AND t.closed_at IS NULL
                JOIN app.users u ON u.id = m.user_id
                WHERE m.role = 'owner'
                ORDER BY t.name, u.email LIMIT 500;
            END IF;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_security_visits(p_days integer)
        RETURNS TABLE (actor_email text, business_id uuid, business_name text,
                       views bigint, changes bigint, last_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            {OWNER_GUARD}
            RETURN QUERY
            SELECT coalesce(l.details->>'email', ''), l.tenant_id, t.name,
                   count(*) FILTER (WHERE l.action IN ('platform.view', 'support.view')),
                   count(*) FILTER (WHERE l.action = 'platform.change'),
                   max(l.occurred_at)
            FROM app.audit_log l JOIN app.tenants t ON t.id = l.tenant_id
            WHERE l.actor_type = 'platform'
              AND l.occurred_at > now() - make_interval(days => least(greatest(p_days, 1), 365))
            GROUP BY l.details->>'email', l.tenant_id, t.name
            ORDER BY max(l.occurred_at) DESC LIMIT 200;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_legal_coverage(p_versions jsonb)
        RETURNS TABLE (document text, version text, accepted bigint, eligible bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            {OWNER_GUARD}
            RETURN QUERY
            SELECT v.key, v.value,
                   (SELECT count(DISTINCT a.user_id) FROM app.legal_acceptances a
                    WHERE a.document = v.key AND a.version = v.value),
                   CASE v.key
                       WHEN 'dpa' THEN (SELECT count(DISTINCT m.user_id)
                                        FROM app.tenant_members m WHERE m.role = 'owner')
                       ELSE (SELECT count(*) FROM app.users)
                   END
            FROM jsonb_each_text(p_versions) v ORDER BY v.key;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_legal_acceptances(p_days integer)
        RETURNS TABLE (accepted_at timestamptz, email text, business_name text, document text,
                       version text, context text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            {OWNER_GUARD}
            RETURN QUERY
            SELECT a.accepted_at, u.email, t.name, a.document, a.version, a.context
            FROM app.legal_acceptances a
            JOIN app.users u ON u.id = a.user_id
            LEFT JOIN app.tenants t ON t.id = a.business_id
            WHERE a.accepted_at > now() - make_interval(days => least(greatest(p_days, 1), 365))
            ORDER BY a.accepted_at DESC LIMIT 200;
        END
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION app.platform_privacy_requests()
        RETURNS TABLE (occurred_at timestamptz, kind text, business_id uuid, business_name text,
                       status text, delete_after timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            {OWNER_GUARD}
            RETURN QUERY
            SELECT * FROM (
                SELECT e.created_at, 'business_export'::text, e.tenant_id, t.name,
                       e.status, NULL::timestamptz
                FROM app.data_exports e JOIN app.tenants t ON t.id = e.tenant_id
                UNION ALL
                SELECT l.occurred_at,
                       CASE l.action WHEN 'clients.erase' THEN 'client_erasure'
                                     ELSE 'client_export' END,
                       l.tenant_id, t.name, 'done', NULL::timestamptz
                FROM app.audit_log l JOIN app.tenants t ON t.id = l.tenant_id
                WHERE l.action IN ('clients.erase', 'clients.export')
                UNION ALL
                SELECT t.closed_at, 'business_closure', t.id, t.name, 'waiting',
                       t.closed_at + interval '90 days'
                FROM app.tenants t WHERE t.closed_at IS NOT NULL
            ) r (occurred_at, kind, business_id, business_name, status, delete_after)
            WHERE r.occurred_at > now() - interval '12 months'
            ORDER BY r.occurred_at DESC LIMIT 200;
        END
        $$
    """)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_api")


def downgrade() -> None:
    # contract: only a rollback drops the functions, and the previous release never calls them.
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION app.{signature}")
