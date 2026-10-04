from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member


def platform_admin(engine: Engine) -> object:
    admin = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'support@mybiz.test')"),
            {"id": admin},
        )
        connection.execute(text("INSERT INTO app.platform_admins VALUES (:id)"), {"id": admin})
    return admin


def test_support_sees_the_business_only_while_access_is_granted(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    admin = platform_admin(engine)
    support = auth(admin, studio["tenant_id"])
    client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"])

    assert client.get("/clients", headers=support).status_code == 403  # no grant yet
    assert client.get("/me", headers=auth(admin)).json()["support_access"] == []

    granted = client.post("/support-access", json={"hours": 2}, headers=studio["headers"])
    assert granted.status_code == 201 and granted.json()["active"] is not None
    me = client.get("/me", headers=auth(admin)).json()
    assert [g["tenant_id"] for g in me["support_access"]] == [str(studio["tenant_id"])]

    tenant = client.get("/tenants/current", headers=support).json()
    assert tenant["role"] == "support"
    assert "clients.read" in tenant["permissions"]
    assert "clients.write" not in tenant["permissions"]
    clients = client.get("/clients", headers=support).json()
    assert [c["first_name"] for c in clients["items"]] == ["Dana"]

    log = client.get("/support-access", headers=studio["headers"]).json()
    assert {v["path"] for v in log["visits"]} >= {"/clients", "/tenants/current"}
    # The email comes from the support user's sign-in profile (synced on /me).
    assert all(v["actor_email"] == f"{admin}@example.com" for v in log["visits"]), log

    client.delete("/support-access", headers=studio["headers"])
    assert client.get("/clients", headers=support).status_code == 403


def test_support_is_read_only(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    admin = platform_admin(engine)
    support = auth(admin, studio["tenant_id"])
    client.post("/support-access", json={"hours": 1}, headers=studio["headers"])

    write = client.post("/clients", json={"first_name": "Mallory"}, headers=support)
    settings = client.patch("/tenants/current", json={"name": "Hacked"}, headers=support)
    grant = client.post("/support-access", json={"hours": 72}, headers=support)

    assert write.status_code == 403 and settings.status_code == 403
    assert grant.status_code == 403  # support can't extend its own access
    assert client.get("/clients", headers=studio["headers"]).json()["total"] == 0


def test_only_owners_grant_and_other_businesses_stay_closed(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    admin = platform_admin(engine)
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={"name": "Other", "vertical": "fitness", "locale": "en",
              "time_zone": "UTC", "currency": "USD"},
        headers=auth(other_owner),
    ).json()  # fmt: skip
    client.post("/support-access", json={"hours": 1}, headers=studio["headers"])

    by_manager = client.post(
        "/support-access", json={"hours": 1}, headers=auth(manager, studio["tenant_id"])
    )
    elsewhere = client.get("/clients", headers=auth(admin, other["id"]))
    not_admin = client.get("/clients", headers=auth(uuid4(), studio["tenant_id"]))

    assert by_manager.status_code == 403
    assert elsewhere.status_code == 403
    assert not_admin.status_code == 403
