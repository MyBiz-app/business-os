from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders


def test_a_new_account_explores_a_sample_business(client: TestClient, auth: AuthHeaders) -> None:
    person = uuid4()

    created = client.post("/tenants/sample", json={"vertical": "barbershop"}, headers=auth(person))

    assert created.status_code == 201, created.text
    tenant_id = created.json()["tenant_id"]
    [membership] = client.get("/me", headers=auth(person)).json()["memberships"]
    assert membership == {"tenant_id": tenant_id, "tenant_name": "ברברשופ לדוגמה", "role": "owner"}
    clients = client.get("/clients", headers=auth(person, tenant_id)).json()
    assert clients["total"] > 0  # filled with fictitious data


def test_only_before_the_first_business(client: TestClient, auth: AuthHeaders) -> None:
    person = uuid4()
    first = client.post("/tenants/sample", json={"vertical": "fitness"}, headers=auth(person))
    assert first.status_code == 201, first.text  # a category: its first kind's services

    again = client.post("/tenants/sample", json={"vertical": "fitness"}, headers=auth(person))

    assert again.status_code == 409 and again.json()["detail"] == "has_business"


def test_only_industries_in_the_catalog(client: TestClient, auth: AuthHeaders) -> None:
    for vertical in ("nope", "pets"):  # unknown, and one that is only planned
        response = client.post(
            "/tenants/sample", json={"vertical": vertical}, headers=auth(uuid4())
        )
        assert response.status_code == 422, vertical
