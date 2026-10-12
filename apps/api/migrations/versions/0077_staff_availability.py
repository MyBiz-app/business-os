"""Shift availability: the weekly hours a person says they can work shifts.

Set by the person in the team app, or by a manager for them. A person with no rows has not said,
so nothing is flagged for them. Kept apart from `staff_hours` (0027), which is when clients can
book appointments with someone. The board warns on a shift outside it, and the coverage report
(coverage rules, 0065) suggests who said they can fill a gap.

Revision ID: 0077
Revises: 0075
Create Date: 2026-10-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0077"
down_revision: str | None = "0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.staff_availability (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            user_id     uuid NOT NULL,
            weekday     smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
            starts      time NOT NULL,
            ends        time NOT NULL CHECK (ends > starts),
            created_at  timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, user_id) REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX staff_availability_user ON app.staff_availability"
        " (tenant_id, user_id, weekday)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.staff_availability TO app_api")
    op.execute("ALTER TABLE app.staff_availability ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY staff_availability_tenant ON app.staff_availability TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)
    # True when the person has said when they can work and the period is not within it. A
    # period past midnight needs the evening up to 23:59 and, the next day, a stretch from 00:00.
    op.execute("""
        CREATE FUNCTION app.outside_availability(
            p_tenant uuid, p_user uuid, p_starts timestamptz, p_ends timestamptz, p_zone text
        ) RETURNS boolean
        LANGUAGE sql STABLE SET search_path = ''
        AS $$
            WITH w AS (
                SELECT a.weekday, a.starts, a.ends FROM app.staff_availability a
                WHERE a.tenant_id = p_tenant AND a.user_id = p_user
            ), p AS (
                SELECT p_starts AT TIME ZONE p_zone AS ls, p_ends AT TIME ZONE p_zone AS le
            )
            SELECT EXISTS (SELECT 1 FROM w) AND NOT EXISTS (
                SELECT 1 FROM w, p
                WHERE w.weekday = extract(isodow FROM p.ls) - 1 AND w.starts <= p.ls::time
                  AND CASE
                      WHEN p.le::date = p.ls::date THEN w.ends >= p.le::time
                      WHEN p.le::time = time '00:00' THEN w.ends >= time '23:59'
                      ELSE w.ends >= time '23:59' AND EXISTS (
                          SELECT 1 FROM w nx
                          WHERE nx.weekday = extract(isodow FROM p.le) - 1
                            AND nx.starts = time '00:00' AND nx.ends >= p.le::time
                      )
                  END
            )
        $$
    """)
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.outside_availability(uuid, uuid, timestamptz, timestamptz,"
        " text) TO app_api"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION app.outside_availability(uuid, uuid, timestamptz, timestamptz, text)")
    op.execute("DROP TABLE app.staff_availability")
