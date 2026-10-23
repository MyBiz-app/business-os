"""Activities per business and per branch (slice C2 of the categories and service model spec).

- `tenant_activities`: what a business offers (a court rental, private lessons, a studio class).
  Each row remembers the business type it came from, because one activity key can mean different
  things in different types (`lesson` on a tennis court is not `lesson` at a driving school).
  Turning one off keeps the row (`enabled`), so history and services that point at it stay valid.
- `location_activities`: which of them each branch offers. A trigger links a new branch to every
  enabled activity, so a branch starts like the business and the owner narrows it later.
- `rooms.resource_type` and `rooms.attributes`: a court or room gets a type from the catalog
  (tennis court, studio) and its own properties (surface, lighting). Filled by the data mapping
  slice; nothing reads them yet.
- `services.activity_id`: the activity a service belongs to.
- `tenant_profile`: the answers the owner gave when setting the business up.

Existing businesses are filled from their industry: the business type that takes over the old
industry key (`successors_of`) gives the starting activities; every branch gets all of them.
This only adds. The rule that a branch kind must stay inside the business's category is lifted
in code, not in the database.

Revision ID: 0156
Revises: 0155
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.catalog.verticals_v2 import default_activities, successors_of

revision: str = "0156"
down_revision: str | None = "0155"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODELS = (
    "appointment",
    "group_class",
    "large_group",
    "resource_rental",
    "resource_staff",
    "open_entry",
    "on_site",
    "project",
)


def upgrade() -> None:
    models = ", ".join(f"'{m}'" for m in MODELS)
    op.execute(f"""
        CREATE TABLE app.tenant_activities (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            business_type  text NOT NULL CHECK (length(trim(business_type)) > 0),
            activity_key   text NOT NULL CHECK (length(trim(activity_key)) > 0),
            model          text NOT NULL CHECK (model IN ({models})),
            resource_type  text,
            position       integer NOT NULL DEFAULT 0,
            enabled        boolean NOT NULL DEFAULT true,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, business_type, activity_key)
        )
    """)
    op.execute("""
        CREATE TABLE app.location_activities (
            tenant_id    uuid NOT NULL,
            location_id  uuid NOT NULL,
            activity_id  uuid NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (location_id, activity_id),
            FOREIGN KEY (tenant_id, location_id)
                REFERENCES app.locations (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, activity_id)
                REFERENCES app.tenant_activities (tenant_id, id) ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX location_activities_location_idx"
        " ON app.location_activities (tenant_id, location_id)"
    )
    op.execute(
        "CREATE INDEX location_activities_activity_idx"
        " ON app.location_activities (tenant_id, activity_id)"
    )
    op.execute("""
        CREATE TABLE app.tenant_profile (
            tenant_id     uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            answers       jsonb NOT NULL DEFAULT '{}'::jsonb,
            completed_at  timestamptz,
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE app.rooms ADD COLUMN resource_type text")
    op.execute("ALTER TABLE app.rooms ADD COLUMN attributes jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE app.services ADD COLUMN activity_id uuid")
    op.execute("""
        ALTER TABLE app.services ADD CONSTRAINT services_activity_fk
            FOREIGN KEY (tenant_id, activity_id)
            REFERENCES app.tenant_activities (tenant_id, id)
    """)
    op.execute("CREATE INDEX services_activity_idx ON app.services (tenant_id, activity_id)")

    op.execute("GRANT SELECT, INSERT, UPDATE ON app.tenant_activities TO app_api")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.location_activities TO app_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON app.tenant_profile TO app_api")
    for table in ("tenant_activities", "location_activities", "tenant_profile"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)

    # A new branch offers everything the business offers; the owner narrows it later.
    op.execute("""
        CREATE FUNCTION app.link_new_location_to_activities() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            INSERT INTO app.location_activities (tenant_id, location_id, activity_id)
            SELECT NEW.tenant_id, NEW.id, a.id
            FROM app.tenant_activities a
            WHERE a.tenant_id = NEW.tenant_id AND a.enabled
            ON CONFLICT DO NOTHING;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER locations_link_activities AFTER INSERT ON app.locations
        FOR EACH ROW EXECUTE FUNCTION app.link_new_location_to_activities()
    """)

    _fill_existing_businesses()


def _fill_existing_businesses() -> None:
    connection = op.get_bind()
    tenants = connection.execute(text("SELECT id, vertical FROM app.tenants")).all()
    for tenant_id, vertical in tenants:
        types = successors_of(vertical)
        if not types:
            continue
        business_type = types[0]["key"]
        for position, activity in enumerate(default_activities(business_type)):
            connection.execute(
                text("""
                    INSERT INTO app.tenant_activities
                        (tenant_id, business_type, activity_key, model, resource_type, position)
                    VALUES (:t, :type, :key, :model, :resource, :position)
                """),
                {
                    "t": tenant_id,
                    "type": business_type,
                    "key": activity["key"],
                    "model": activity["model"],
                    "resource": activity.get("resource_type"),
                    "position": position,
                },
            )
    op.execute("""
        INSERT INTO app.location_activities (tenant_id, location_id, activity_id)
        SELECT l.tenant_id, l.id, a.id
        FROM app.locations l
        JOIN app.tenant_activities a ON a.tenant_id = l.tenant_id
    """)
    # A class service belongs to the business's group activity, an appointment service to its
    # one-to-one activity; anything else stays unassigned until the data mapping slice.
    for booking_mode, wanted in (
        ("class", ("group_class", "large_group")),
        ("appointment", ("appointment",)),
    ):
        connection.execute(
            text("""
                UPDATE app.services s SET activity_id = (
                    SELECT a.id FROM app.tenant_activities a
                    WHERE a.tenant_id = s.tenant_id AND a.model = ANY(CAST(:wanted AS text[]))
                    ORDER BY a.position LIMIT 1)
                WHERE s.booking_mode = :mode
            """),
            {"mode": booking_mode, "wanted": list(wanted)},
        )


def downgrade() -> None:
    # contract: only a rollback drops these, and the previous release never reads them.
    op.execute("DROP TRIGGER locations_link_activities ON app.locations")
    op.execute("DROP FUNCTION app.link_new_location_to_activities()")
    op.execute("ALTER TABLE app.services DROP COLUMN activity_id")
    op.execute("ALTER TABLE app.rooms DROP COLUMN attributes, DROP COLUMN resource_type")
    op.execute("DROP TABLE app.tenant_profile, app.location_activities, app.tenant_activities")
