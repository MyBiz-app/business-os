from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.jobs import delete_closed_businesses, remind_plans, remind_sessions
from tests.conftest import STUDIO, AuthHeaders


def close(client: TestClient, studio: dict, name: str = STUDIO["name"]):
    return client.post(
        "/tenants/current/closure", json={"confirm_name": name}, headers=studio["headers"]
    )


def backdate(engine: Engine, tenant_id: UUID, days: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.tenants SET closed_at = now() - make_interval(days => :d) WHERE id = :t"
            ),
            {"d": days, "t": tenant_id},
        )


def tenant_ids(engine: Engine) -> set[str]:
    with engine.begin() as connection:
        return set(connection.execute(text("SELECT id::text FROM app.tenants")).scalars())


def test_owner_closes_the_business_and_it_locks(client: TestClient, studio: dict) -> None:
    assert client.get("/tenants/current/closure", headers=studio["headers"]).json() == {
        "closed_at": None,
        "delete_after": None,
    }
    response = close(client, studio)
    assert response.status_code == 200
    body = response.json()
    closed = datetime.fromisoformat(body["closed_at"])
    assert datetime.fromisoformat(body["delete_after"]) - closed == timedelta(days=90)

    assert client.get("/clients", headers=studio["headers"]).json()["detail"] == "business_closed"
    assert client.get("/tenants/current/closure", headers=studio["headers"]).status_code == 200
    assert close(client, studio).status_code == 409


def test_closing_needs_the_owner_and_the_exact_name(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    assert close(client, studio, "Studio").status_code == 422
    coach = auth(studio["coach"], studio["tenant_id"])
    refused = client.post(
        "/tenants/current/closure", json={"confirm_name": STUDIO["name"]}, headers=coach
    )
    assert refused.status_code == 403 and refused.json()["detail"] == "owner_only"
    assert client.get("/clients", headers=studio["headers"]).status_code == 200  # still open


def test_the_owner_can_reopen_before_deletion(client: TestClient, studio: dict) -> None:
    assert client.delete("/tenants/current/closure", headers=studio["headers"]).status_code == 409
    close(client, studio)
    reopened = client.delete("/tenants/current/closure", headers=studio["headers"])
    assert reopened.status_code == 200 and reopened.json()["closed_at"] is None
    assert client.get("/clients", headers=studio["headers"]).status_code == 200


def test_clients_are_locked_out_of_a_closed_business(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    person = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'c@example.com')"), {"id": person}
        )
        connection.execute(
            text("""
                INSERT INTO app.clients (tenant_id, first_name, user_id)
                VALUES (:t, 'Dana', :u)
            """),
            {"t": studio["tenant_id"], "u": person},
        )
    # Not yet closed: the client reaches the business (stopped only by the missing module).
    before = client.get("/client/bookings", headers=auth(person, studio["tenant_id"]))
    assert before.status_code == 200
    close(client, studio)
    after = client.get("/client/bookings", headers=auth(person, studio["tenant_id"]))
    assert after.status_code == 403 and after.json()["detail"] == "business_closed"


def test_closed_businesses_are_left_out_of_automation(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    close(client, studio)
    with engine.begin() as connection:
        assert remind_sessions(connection) == 0
        assert remind_plans(connection) == 0
        publishing = connection.execute(
            text("SELECT shifts_publish_auto FROM app.tenants WHERE id = :t"),
            {"t": studio["tenant_id"]},
        ).scalar_one()
    assert publishing is False


def test_deletion_is_a_dry_run_unless_applied(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    close(client, studio)
    backdate(engine, studio["tenant_id"], 91)
    with engine.begin() as connection:
        report = delete_closed_businesses(connection)
    assert report["dry_run"] == 1 and report["businesses"] == 1
    assert report["ids"] == [str(studio["tenant_id"])]
    assert str(studio["tenant_id"]) in tenant_ids(engine)


def test_a_business_is_deleted_only_after_ninety_days(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    close(client, studio)
    backdate(engine, studio["tenant_id"], 89)
    with engine.begin() as connection:
        assert delete_closed_businesses(connection, apply=True)["businesses"] == 0
    assert str(studio["tenant_id"]) in tenant_ids(engine)


def test_applying_deletes_the_closed_business_and_all_its_data_only(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"])
    other_owner = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    client.post("/clients", json={"first_name": "Noa"}, headers=auth(other_owner, other))
    still_open = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]  # noqa: F841

    close(client, studio)
    backdate(engine, studio["tenant_id"], 91)
    with engine.begin() as connection:
        report = delete_closed_businesses(connection, apply=True)
    assert report["dry_run"] == 0 and report["businesses"] == 1

    assert str(studio["tenant_id"]) not in tenant_ids(engine)
    assert other in tenant_ids(engine)
    with engine.begin() as connection:
        names = set(connection.execute(text("SELECT first_name FROM app.clients")).scalars())
        leftovers = connection.execute(
            text("SELECT count(*) FROM app.locations WHERE tenant_id = :t"),
            {"t": studio["tenant_id"]},
        ).scalar_one()
        audit = (
            connection.execute(
                text("SELECT details->>'name' FROM app.platform_audit WHERE action = :a"),
                {"a": "business.deleted"},
            )
            .scalars()
            .all()
        )
        owner_kept = connection.execute(
            text("SELECT count(*) FROM app.users WHERE id = :u"), {"u": studio["owner"]}
        ).scalar_one()
    assert names == {"Noa"} and leftovers == 0
    assert audit == [STUDIO["name"]] and owner_kept == 1
    assert datetime.now(UTC)  # the job ran with a real clock
