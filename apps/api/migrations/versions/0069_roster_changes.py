"""Emailing staff when a shift they were told about changes or is taken away.

A trigger on `app.shifts` records the "before" picture of every edit or removal of a published
shift whose owner was already emailed (`shift_changes`); the notify-shifts job later sends one
email per person once the edits go quiet. A shift handed to another person is re-announced to
them through the normal publish email (`notified_at` is reset) and counts as removed for the
previous person. Past shifts and drafts are never recorded.

Revision ID: 0069
Revises: 0068
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.shift_changes (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id        uuid NOT NULL,
            shift_id       uuid NOT NULL,
            before_starts  timestamptz NOT NULL,
            before_ends    timestamptz NOT NULL,
            before_branch  text NOT NULL,
            before_position text,
            created_at     timestamptz NOT NULL DEFAULT now(),
            handled_at     timestamptz
        )
    """)
    op.execute(
        "CREATE INDEX shift_changes_pending ON app.shift_changes (tenant_id, user_id, created_at)"
        " WHERE handled_at IS NULL"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.shift_changes TO app_api")
    op.execute("ALTER TABLE app.shift_changes ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY shift_changes_tenant ON app.shift_changes TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    op.execute("""
        CREATE FUNCTION app.record_shift_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        BEGIN
            IF OLD.published_at IS NULL OR OLD.notified_at IS NULL OR OLD.ends_at <= now() THEN
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' AND NOT (
                OLD.user_id IS DISTINCT FROM NEW.user_id
                OR OLD.location_id IS DISTINCT FROM NEW.location_id
                OR OLD.starts_at IS DISTINCT FROM NEW.starts_at
                OR OLD.ends_at IS DISTINCT FROM NEW.ends_at
                OR OLD.position IS DISTINCT FROM NEW.position
            ) THEN
                RETURN NEW;
            END IF;
            -- During a cascade (a business or person being removed) there is nobody to tell.
            IF EXISTS (SELECT 1 FROM app.tenants WHERE id = OLD.tenant_id)
               AND EXISTS (SELECT 1 FROM app.tenant_members
                           WHERE tenant_id = OLD.tenant_id AND user_id = OLD.user_id) THEN
                INSERT INTO app.shift_changes (tenant_id, user_id, shift_id, before_starts,
                                               before_ends, before_branch, before_position)
                SELECT OLD.tenant_id, OLD.user_id, OLD.id, OLD.starts_at, OLD.ends_at,
                       l.name, OLD.position
                FROM app.locations l
                WHERE l.tenant_id = OLD.tenant_id AND l.id = OLD.location_id;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.user_id IS DISTINCT FROM NEW.user_id THEN
                    NEW.notified_at := NULL;  -- the new person gets the publish email
                END IF;
                RETURN NEW;
            END IF;
            RETURN OLD;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER shifts_record_change BEFORE UPDATE OR DELETE ON app.shifts
        FOR EACH ROW EXECUTE FUNCTION app.record_shift_change()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER shifts_record_change ON app.shifts")
    op.execute("DROP FUNCTION app.record_shift_change()")
    op.execute("DROP TABLE app.shift_changes")
