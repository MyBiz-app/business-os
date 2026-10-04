from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import new_client


def test_custom_role_defines_member_permissions(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = studio["headers"]
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, "staff")
    member_headers = auth(member, studio["tenant_id"])
    assert (
        client.post("/clients", json={"first_name": "A"}, headers=member_headers).status_code == 403
    )

    role = client.post(
        "/roles",
        json={"name": "Sales", "permissions": ["clients.read", "clients.write", "sales.manage"]},
        headers=owner,
    )
    assert role.status_code == 201, role.text
    assigned = client.patch(
        f"/staff/{member}", json={"custom_role_id": role.json()["id"]}, headers=owner
    )
    assert assigned.status_code == 200
    assert assigned.json()["custom_role_name"] == "Sales"
    assert assigned.json()["role"] == "staff"

    assert (
        client.post("/clients", json={"first_name": "A"}, headers=member_headers).status_code == 201
    )
    # The custom role replaces the system bundle: no schedule access any more.
    assert (
        client.get("/sessions", params={"start": "2026-10-11"}, headers=member_headers).status_code
        == 403
    )
    tenant = client.get("/tenants/current", headers=member_headers).json()
    assert tenant["permissions"] == ["clients.read", "clients.write", "sales.manage"]
    assert tenant["custom_role_name"] == "Sales"

    listing = client.get("/roles", headers=owner).json()
    assert [r["members"] for r in listing["custom"]] == [1]
    assert "ai.use" in listing["permissions"]
    assert client.delete(f"/roles/{role.json()['id']}", headers=owner).status_code == 409

    back = client.patch(f"/staff/{member}", json={"role": "front_desk"}, headers=owner)
    assert back.json()["custom_role_id"] is None
    assert client.delete(f"/roles/{role.json()['id']}", headers=owner).status_code == 204


def test_no_privilege_escalation(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = studio["headers"]
    hr = client.post(
        "/roles",
        json={"name": "Team lead", "permissions": ["staff.read", "staff.manage", "clients.read"]},
        headers=owner,
    ).json()
    lead, other = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], lead, "staff")
    add_member(engine, studio["tenant_id"], other, "staff")
    client.patch(f"/staff/{lead}", json={"custom_role_id": hr["id"]}, headers=owner)
    lead_headers = auth(lead, studio["tenant_id"])

    # A team lead cannot create or hand out permissions they don't have...
    too_much = client.post(
        "/roles", json={"name": "Boss", "permissions": ["business.settings"]}, headers=lead_headers
    )
    assert too_much.status_code == 403
    assert too_much.json()["detail"] == "exceeds_own_permissions"
    edit = client.patch(
        f"/roles/{hr['id']}",
        json={"permissions": ["staff.manage", "reports.read"]},
        headers=lead_headers,
    )
    assert edit.status_code == 403
    # ...cannot change their own role, and cannot make anyone an owner.
    self_change = client.patch(f"/staff/{lead}", json={"role": "manager"}, headers=lead_headers)
    assert self_change.json()["detail"] == "cannot_change_own_role"
    promote = client.patch(f"/staff/{other}", json={"role": "owner"}, headers=lead_headers)
    assert promote.status_code == 403
    # But can give others roles within their own permissions.
    fine = client.post(
        "/roles", json={"name": "Viewer", "permissions": ["clients.read"]}, headers=lead_headers
    )
    assert fine.status_code == 201
    assert (
        client.patch(
            f"/staff/{other}", json={"custom_role_id": fine.json()["id"]}, headers=lead_headers
        ).status_code
        == 200
    )


def test_role_validation_and_isolation(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    owner = studio["headers"]
    assert (
        client.post(
            "/roles", json={"name": "X", "permissions": ["nope"]}, headers=owner
        ).status_code
        == 422
    )
    client.post("/roles", json={"name": "Desk", "permissions": []}, headers=owner)
    duplicate = client.post("/roles", json={"name": "desk", "permissions": []}, headers=owner)
    assert duplicate.status_code == 409
    owners_custom = client.patch(
        f"/staff/{studio['owner']}",
        json={"custom_role_id": client.get("/roles", headers=owner).json()["custom"][0]["id"]},
        headers=owner,
    )
    assert owners_custom.status_code == 409  # the last owner keeps the owner role

    other_owner = uuid4()
    from tests.conftest import STUDIO

    other = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    assert client.get("/roles", headers=auth(other_owner, other)).json()["custom"] == []
    new_client(client, owner, "Dana")
