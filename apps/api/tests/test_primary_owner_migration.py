import importlib.util
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, text

MIGRATION = Path(__file__).parent.parent / "migrations/versions/0062_primary_owner_no_businesses.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0062", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_primary_owner_businesses_move_to_the_demo_account(engine: Engine, studio: dict) -> None:
    migration = load_migration()
    demo = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.users SET email = :e WHERE id = :id"),
            {"e": migration.PRIMARY_OWNER, "id": studio["owner"]},
        )
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :e)"),
            {"id": demo, "e": migration.DEMO_ACCOUNT},
        )
        connection.execute(text(migration.MOVE_MEMBERSHIPS))
        members = {
            row.user_id: row.role
            for row in connection.execute(
                text("SELECT user_id, role FROM app.tenant_members WHERE tenant_id = :t"),
                {"t": studio["tenant_id"]},
            )
        }
    assert members[demo] == "owner"
    assert studio["owner"] not in members
    assert members[studio["coach"]] == "staff"  # the rest of the team stays
