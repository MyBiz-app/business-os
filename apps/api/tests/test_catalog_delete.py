from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import new_client
from tests.test_plans import card, sell


def test_unused_items_are_deleted_and_used_ones_archived(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]

    unused = client.post(
        "/services", json={"name": "Trial", "duration_minutes": 30}, headers=headers
    )
    assert client.delete(f"/services/{unused.json()['id']}", headers=headers).json() == {
        "result": "deleted"
    }
    assert client.get(f"/services/{unused.json()['id']}", headers=headers).status_code == 404

    # The studio's own service has a session (or will once used): archive keeps history intact.
    client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": "2026-10-12",
            "start_time": "18:00",
            "location_id": studio["location"]["id"],
            "room_id": studio["room"]["id"],
            "instructor_user_id": str(studio["coach"]),
        },
        headers=headers,
    )
    result = client.delete(f"/services/{studio['service']['id']}", headers=headers)
    assert result.json() == {"result": "archived"}
    assert (
        client.get(f"/services/{studio['service']['id']}", headers=headers).json()["active"]
        is False
    )

    plan = card(client, headers)
    sell(client, headers, new_client(client, headers, "Dana"), plan["id"])
    assert client.delete(f"/plans/{plan['id']}", headers=headers).json() == {"result": "archived"}
    assert client.get(f"/plans/{plan['id']}", headers=headers).json()["active"] is False
    fresh = card(client, headers, credits=3)
    assert client.delete(f"/plans/{fresh['id']}", headers=headers).json() == {"result": "deleted"}
    assert client.delete(f"/plans/{uuid4()}", headers=headers).status_code == 404


def test_only_owners_and_managers_may_delete(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = studio["headers"]
    service = client.post("/services", json={"name": "Old", "duration_minutes": 30}, headers=owner)
    plan = card(client, owner)
    for role in ("staff", "front_desk"):
        member = uuid4()
        add_member(engine, studio["tenant_id"], member, role)
        headers = auth(member, studio["tenant_id"])
        assert (
            client.delete(f"/services/{service.json()['id']}", headers=headers).status_code == 403
        )
        assert client.delete(f"/plans/{plan['id']}", headers=headers).status_code == 403
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    boss = auth(manager, studio["tenant_id"])
    assert client.delete(f"/plans/{plan['id']}", headers=boss).status_code == 200
    assert client.delete(f"/services/{service.json()['id']}", headers=boss).status_code == 200


def test_members_list_their_effective_permissions(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    owner = studio["headers"]
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, "staff")
    role = client.post(
        "/roles",
        json={"name": "Desk", "permissions": ["clients.read", "sales.manage"]},
        headers=owner,
    ).json()
    client.patch(f"/staff/{member}", json={"custom_role_id": role["id"]}, headers=owner)
    members = {m["user_id"]: m for m in client.get("/staff", headers=owner).json()["members"]}
    assert members[str(member)]["permissions"] == ["clients.read", "sales.manage"]
    owners = [m for m in members.values() if m["role"] == "owner"]
    assert "catalog.delete" in owners[0]["permissions"]
