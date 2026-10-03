from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, TokenFactory

STUDIO = {
    "name": "Studio Flow",
    "vertical": "fitness",
    "locale": "he",
    "time_zone": "Asia/Jerusalem",
    "currency": "ILS",
}


def test_create_tenant_makes_the_creator_its_owner(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()

    response = client.post("/tenants", json=STUDIO, headers=auth(owner))

    assert response.status_code == 201
    tenant = response.json()
    assert tenant["name"] == "Studio Flow"
    assert tenant["role"] == "owner"

    me = client.get("/me", headers=auth(owner)).json()
    assert me["id"] == str(owner)
    assert me["memberships"] == [
        {"tenant_id": tenant["id"], "tenant_name": "Studio Flow", "role": "owner"}
    ]


def test_member_can_read_current_tenant(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    tenant_id = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"]

    response = client.get("/tenants/current", headers=auth(owner, tenant_id))

    assert response.status_code == 200
    assert response.json()["id"] == tenant_id


def test_new_user_has_no_memberships(client: TestClient, auth: AuthHeaders) -> None:
    response = client.get("/me", headers=auth(uuid4()))

    assert response.status_code == 200
    assert response.json()["memberships"] == []


def test_rejects_invalid_tenant_input(client: TestClient, auth: AuthHeaders) -> None:
    user = uuid4()
    for field, value in [
        ("time_zone", "Mars/Olympus"),
        ("vertical", "spaceship"),
        ("currency", "ils"),
        ("name", "   "),
        ("locale", "fr"),
    ]:
        response = client.post("/tenants", json={**STUDIO, field: value}, headers=auth(user))
        assert response.status_code == 422, field


def test_requires_a_valid_token(client: TestClient, make_token: TokenFactory) -> None:
    assert client.get("/me").status_code == 401

    foreign_key = ec.generate_private_key(ec.SECP256R1())
    forged = make_token(uuid4(), key=foreign_key)
    assert client.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
