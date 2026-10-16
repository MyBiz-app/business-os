"""Branch managers (round 5, G2): a role that has manager rights only at its own branches.

`tenant_members.role` and `invitations.role` accept `branch_manager`. The member's `location_ids`
are the branches they manage, and the API refuses a branch manager with none. A branch records
who manages it (`locations.manager_user_id`; the business's owner until someone is appointed), and
an invitation can carry the branches the new member will be kept to, so a branch manager can only
invite people into their own branches.

Revision ID: 0086
Revises: 0085
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0086"
down_revision: str | None = "0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = "'owner', 'manager', 'staff', 'front_desk'"
NEW_ROLES = "'owner', 'manager', 'branch_manager', 'staff', 'front_desk'"

ACCEPT_INVITATION = """
    CREATE OR REPLACE FUNCTION app.accept_invitation(p_token_hash text) RETURNS uuid
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
        INSERT INTO app.tenant_members (tenant_id, user_id, role, location_ids)
        VALUES (v_invite.tenant_id, v_user_id, v_invite.role, v_invite.location_ids)
        ON CONFLICT (tenant_id, user_id) DO NOTHING;
        UPDATE app.invitations SET accepted_at = now() WHERE id = v_invite.id;
        RETURN v_invite.tenant_id;
    END
    $$
"""

OLD_ACCEPT_INVITATION = ACCEPT_INVITATION.replace(
    "(tenant_id, user_id, role, location_ids)", "(tenant_id, user_id, role)"
).replace("v_invite.role, v_invite.location_ids", "v_invite.role")


def upgrade() -> None:
    for table in ("tenant_members", "invitations"):
        op.execute(f"ALTER TABLE app.{table} DROP CONSTRAINT {table}_role_check")
        op.execute(
            f"ALTER TABLE app.{table} ADD CONSTRAINT {table}_role_check "
            f"CHECK (role IN ({NEW_ROLES}))"
        )
    op.execute("ALTER TABLE app.invitations ADD COLUMN location_ids uuid[] NOT NULL DEFAULT '{}'")
    op.execute(ACCEPT_INVITATION)
    op.execute(
        "ALTER TABLE app.locations ADD COLUMN manager_user_id uuid REFERENCES app.users (id)"
    )
    # Until someone is appointed, the branch is managed by the business's first owner.
    op.execute("""
        UPDATE app.locations l SET manager_user_id = (
            SELECT m.user_id FROM app.tenant_members m
            WHERE m.tenant_id = l.tenant_id AND m.role = 'owner'
            ORDER BY m.created_at LIMIT 1
        )
    """)
    # A new branch starts with the business's owner as its manager; the first owner of a business
    # (created after its first branch at sign-up) takes over the branches that have none.
    op.execute("""
        CREATE FUNCTION app.default_branch_manager() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            IF NEW.manager_user_id IS NULL THEN
                SELECT m.user_id INTO NEW.manager_user_id FROM app.tenant_members m
                WHERE m.tenant_id = NEW.tenant_id AND m.role = 'owner'
                ORDER BY m.created_at LIMIT 1;
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER locations_default_manager BEFORE INSERT ON app.locations
        FOR EACH ROW EXECUTE FUNCTION app.default_branch_manager()
    """)
    op.execute("""
        CREATE FUNCTION app.owner_manages_unmanaged_branches() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
        AS $$
        BEGIN
            UPDATE app.locations SET manager_user_id = NEW.user_id
            WHERE tenant_id = NEW.tenant_id AND manager_user_id IS NULL;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER tenant_members_first_owner AFTER INSERT ON app.tenant_members
        FOR EACH ROW WHEN (NEW.role = 'owner')
        EXECUTE FUNCTION app.owner_manages_unmanaged_branches()
    """)
    op.execute("""
        CREATE INDEX locations_manager ON app.locations (tenant_id, manager_user_id)
        WHERE manager_user_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER tenant_members_first_owner ON app.tenant_members")
    op.execute("DROP FUNCTION app.owner_manages_unmanaged_branches()")
    op.execute("DROP TRIGGER locations_default_manager ON app.locations")
    op.execute("DROP FUNCTION app.default_branch_manager()")
    op.execute("DROP INDEX app.locations_manager")
    op.execute("ALTER TABLE app.locations DROP COLUMN manager_user_id")
    op.execute(OLD_ACCEPT_INVITATION)
    op.execute("ALTER TABLE app.invitations DROP COLUMN location_ids")
    op.execute("UPDATE app.tenant_members SET role = 'staff' WHERE role = 'branch_manager'")
    op.execute("DELETE FROM app.invitations WHERE role = 'branch_manager'")
    for table in ("tenant_members", "invitations"):
        op.execute(f"ALTER TABLE app.{table} DROP CONSTRAINT {table}_role_check")
        op.execute(
            f"ALTER TABLE app.{table} ADD CONSTRAINT {table}_role_check "
            f"CHECK (role IN ({OLD_ROLES}))"
        )
