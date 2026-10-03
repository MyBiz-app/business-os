"""Staff invitations, and letting members see each other's profiles.

An invitation is a one-time link (only its SHA-256 hash is stored). Accepting requires the
signed-in user's email to match the invited email.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.invitations (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            email        text NOT NULL,
            role         text NOT NULL CHECK (role IN ('owner', 'manager', 'staff', 'front_desk')),
            token_hash   text NOT NULL UNIQUE,
            invited_by   uuid REFERENCES app.users (id) ON DELETE SET NULL,
            expires_at   timestamptz NOT NULL,
            accepted_at  timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX invitations_tenant_idx ON app.invitations (tenant_id, created_at)")
    op.execute("GRANT SELECT, INSERT, DELETE ON app.invitations TO app_api")
    op.execute("ALTER TABLE app.invitations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY invitations_tenant ON app.invitations TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    # Members of the current tenant can see each other's basic profile (name, email).
    op.execute("""
        CREATE POLICY users_same_tenant ON app.users FOR SELECT TO app_api
        USING (EXISTS (
            SELECT 1 FROM app.tenant_members m
            WHERE m.user_id = app.users.id AND m.tenant_id = app.current_tenant_id()
        ))
    """)

    # The invitee is not a member yet, so RLS hides the invitation; these two functions are
    # the only way in, and only with the secret token.
    op.execute("""
        CREATE FUNCTION app.invitation_preview(p_token_hash text)
        RETURNS TABLE (tenant_name text, role text, email text, status text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
        AS $$
            SELECT t.name, i.role, i.email,
                   CASE WHEN i.accepted_at IS NOT NULL THEN 'accepted'
                        WHEN i.expires_at < now() THEN 'expired'
                        ELSE 'pending' END
            FROM app.invitations i JOIN app.tenants t ON t.id = i.tenant_id
            WHERE i.token_hash = p_token_hash
        $$
    """)
    op.execute("""
        CREATE FUNCTION app.accept_invitation(p_token_hash text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        DECLARE
            v_user_id uuid := app.current_user_id();
            v_invite app.invitations;
        BEGIN
            SELECT * INTO v_invite FROM app.invitations
            WHERE token_hash = p_token_hash FOR UPDATE;
            IF v_invite.id IS NULL THEN
                RAISE EXCEPTION 'invitation_not_found' USING ERRCODE = 'P0002';
            END IF;
            IF v_invite.accepted_at IS NOT NULL OR v_invite.expires_at < now() THEN
                RAISE EXCEPTION 'invitation_not_pending' USING ERRCODE = 'P0001';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM app.users u
                WHERE u.id = v_user_id AND lower(u.email) = lower(v_invite.email)
            ) THEN
                RAISE EXCEPTION 'invitation_email_mismatch' USING ERRCODE = '42501';
            END IF;
            INSERT INTO app.tenant_members (tenant_id, user_id, role)
            VALUES (v_invite.tenant_id, v_user_id, v_invite.role)
            ON CONFLICT (tenant_id, user_id) DO NOTHING;
            UPDATE app.invitations SET accepted_at = now() WHERE id = v_invite.id;
            RETURN v_invite.tenant_id;
        END
        $$
    """)
    for signature in ("invitation_preview(text)", "accept_invitation(text)"):
        op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.accept_invitation(text), app.invitation_preview(text)")
    op.execute("DROP POLICY users_same_tenant ON app.users")
    op.execute("DROP TABLE app.invitations")
