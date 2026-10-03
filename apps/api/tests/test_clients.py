from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_tenants import STUDIO


@pytest.fixture
def studio(client: TestClient, auth: AuthHeaders) -> dict[str, UUID]:
    owner = uuid4()
    tenant_id = UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
    return {"owner": owner, "tenant_id": tenant_id}


def test_create_and_read_client(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])

    created = client.post(
        "/clients",
        json={
            "first_name": " Dana ",
            "last_name": "Levi",
            "email": "dana@example.com",
            "phone": "",
        },
        headers=headers,
    )

    assert created.status_code == 201
    body = created.json()
    assert body["first_name"] == "Dana"
    assert body["phone"] is None
    assert body["status"] == "active"
    fetched = client.get(f"/clients/{body['id']}", headers=headers)
    assert fetched.json() == body


def test_list_searches_and_paginates(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    for first, last in [("Dana", "Levi"), ("Noa", "Cohen"), ("Dan", "Mizrahi"), ("יעל", "כהן")]:
        client.post("/clients", json={"first_name": first, "last_name": last}, headers=headers)

    everyone = client.get("/clients", headers=headers).json()
    dan = client.get("/clients", params={"search": "dan"}, headers=headers).json()
    cohen_he = client.get("/clients", params={"search": "כהן"}, headers=headers).json()
    page = client.get("/clients", params={"limit": 2, "offset": 2}, headers=headers).json()
    wildcard = client.get("/clients", params={"search": "%"}, headers=headers).json()

    assert everyone["total"] == 4
    assert sorted(c["first_name"] for c in dan["items"]) == ["Dan", "Dana"]
    assert [c["first_name"] for c in cohen_he["items"]] == ["יעל"]
    assert page["total"] == 4 and len(page["items"]) == 2
    assert wildcard["total"] == 0


def test_update_client(client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    client_id = client.post("/clients", json={"first_name": "Dana"}, headers=headers).json()["id"]

    response = client.patch(
        f"/clients/{client_id}",
        json={"status": "inactive", "notes": "Knee injury", "first_name": "Dana R."},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "inactive"
    assert response.json()["notes"] == "Knee injury"
    assert response.json()["first_name"] == "Dana R."


def test_email_is_unique_per_business(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    client.post("/clients", json={"first_name": "A", "email": "a@example.com"}, headers=headers)

    duplicate = client.post(
        "/clients", json={"first_name": "B", "email": "A@Example.com"}, headers=headers
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "email_taken"


def test_rejects_invalid_input(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    for body in [{"first_name": "  "}, {"first_name": "A", "email": "nope"}, {"last_name": "B"}]:
        assert client.post("/clients", json=body, headers=headers).status_code == 422


def test_staff_can_read_but_not_write(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    staff = uuid4()
    add_member(engine, studio["tenant_id"], staff, "staff")
    owner_headers = auth(studio["owner"], studio["tenant_id"])
    client_id = client.post("/clients", json={"first_name": "Dana"}, headers=owner_headers).json()[
        "id"
    ]
    staff_headers = auth(staff, studio["tenant_id"])

    assert client.get("/clients", headers=staff_headers).status_code == 200
    assert (
        client.post("/clients", json={"first_name": "X"}, headers=staff_headers).status_code == 403
    )
    patch = client.patch(f"/clients/{client_id}", json={"notes": "x"}, headers=staff_headers)
    assert patch.status_code == 403


def test_front_desk_can_write(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")

    response = client.post(
        "/clients", json={"first_name": "Walk-in"}, headers=auth(desk, studio["tenant_id"])
    )

    assert response.status_code == 201


def test_clients_are_isolated_between_businesses(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    mine = auth(studio["owner"], studio["tenant_id"])
    theirs = auth(other_owner, other_tenant)
    client_id = client.post("/clients", json={"first_name": "Dana"}, headers=mine).json()["id"]

    assert client.get("/clients", headers=theirs).json()["total"] == 0
    assert client.get(f"/clients/{client_id}", headers=theirs).status_code == 404
    patch = client.patch(f"/clients/{client_id}", json={"notes": "x"}, headers=theirs)
    assert patch.status_code == 404
    # Same email is fine in another business.
    client.post("/clients", json={"first_name": "A", "email": "a@example.com"}, headers=mine)
    other = client.post(
        "/clients", json={"first_name": "A", "email": "a@example.com"}, headers=theirs
    )
    assert other.status_code == 201
    # Using my tenant id with their user is refused outright.
    forged = client.get("/clients", headers=auth(other_owner, studio["tenant_id"]))
    assert forged.status_code == 403
