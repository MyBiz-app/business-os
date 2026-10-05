from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.core.db import open_session
from tests.conftest import AuthHeaders, add_member
from tests.test_tenants import STUDIO


@pytest.fixture
def studio(client: TestClient, auth: AuthHeaders) -> dict[str, UUID]:
    owner = uuid4()
    tenant_id = UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
    return {"owner": owner, "tenant_id": tenant_id}


def owner_headers(auth: AuthHeaders, studio: dict[str, UUID]) -> dict[str, str]:
    return auth(studio["owner"], studio["tenant_id"])


def test_service_defaults_to_business_currency(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    response = client.post(
        "/services",
        json={"name": "Pilates Mat", "duration_minutes": 55, "capacity": 12, "price_amount": 6000},
        headers=owner_headers(auth, studio),
    )

    assert response.status_code == 201
    service = response.json()
    assert service["price_currency"] == "ILS"
    assert service["price_amount"] == 6000
    assert service["active"] is True


def test_update_and_filter_services(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = owner_headers(auth, studio)
    yoga = client.post(
        "/services", json={"name": "Yoga", "duration_minutes": 60}, headers=headers
    ).json()
    client.post("/services", json={"name": "Personal", "duration_minutes": 45}, headers=headers)

    updated = client.patch(
        f"/services/{yoga['id']}",
        json={"active": False, "color": "#22AA88", "description": " ", "name": None},
        headers=headers,
    )
    active = client.get("/services", params={"active": True}, headers=headers).json()

    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["name"] == "Yoga"
    assert updated.json()["description"] is None
    assert [s["name"] for s in active] == ["Personal"]


def test_rejects_invalid_services(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = owner_headers(auth, studio)
    for body in [
        {"name": "X", "duration_minutes": 0},
        {"name": "X", "duration_minutes": 30, "capacity": 0},
        {"name": "X", "duration_minutes": 30, "price_amount": -1},
        {"name": "X", "duration_minutes": 30, "color": "red"},
        {"name": " ", "duration_minutes": 30},
    ]:
        assert client.post("/services", json=body, headers=headers).status_code == 422, body


def test_locations_with_rooms(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = owner_headers(auth, studio)
    location = client.post(
        "/locations", json={"name": "Tel Aviv", "address": "Dizengoff 100"}, headers=headers
    ).json()

    room = client.post(
        f"/locations/{location['id']}/rooms",
        json={"name": "Studio A", "capacity": 14},
        headers=headers,
    )
    renamed = client.patch(
        f"/rooms/{room.json()['id']}", json={"name": "Big room"}, headers=headers
    )
    fetched = client.get(f"/locations/{location['id']}", headers=headers).json()
    closed = client.patch(f"/locations/{location['id']}", json={"active": False}, headers=headers)

    assert room.status_code == 201
    assert renamed.json()["name"] == "Big room"
    assert [r["name"] for r in fetched["rooms"]] == ["Big room"]
    assert closed.json()["active"] is False
    listed = {loc["id"]: loc for loc in client.get("/locations", headers=headers).json()}
    assert listed[location["id"]]["rooms"][0]["capacity"] == 14


def test_catalog_permissions(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    desk, manager = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    add_member(engine, studio["tenant_id"], manager, "manager")
    service = {"name": "Yoga", "duration_minutes": 60}

    desk_headers = auth(desk, studio["tenant_id"])
    assert client.get("/services", headers=desk_headers).status_code == 200
    assert client.post("/services", json=service, headers=desk_headers).status_code == 403
    assert client.post("/locations", json={"name": "X"}, headers=desk_headers).status_code == 403
    manager_headers = auth(manager, studio["tenant_id"])
    assert client.post("/services", json=service, headers=manager_headers).status_code == 201


def test_catalog_is_isolated_between_businesses(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    mine = owner_headers(auth, studio)
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    theirs = auth(other_owner, other_tenant)
    service = client.post(
        "/services", json={"name": "Yoga", "duration_minutes": 60}, headers=mine
    ).json()
    location = client.post("/locations", json={"name": "Mine"}, headers=mine).json()

    assert client.get("/services", headers=theirs).json() == []
    assert client.get(f"/services/{service['id']}", headers=theirs).status_code == 404
    # They see only their own main branch.
    assert location["id"] not in {
        loc["id"] for loc in client.get("/locations", headers=theirs).json()
    }
    # They cannot add a room to my location, through the API or directly in the database.
    room = client.post(f"/locations/{location['id']}/rooms", json={"name": "X"}, headers=theirs)
    assert room.status_code == 404
    with (
        open_session(engine, other_owner, UUID(other_tenant)) as session,
        pytest.raises(DBAPIError, match=r"foreign key|row-level security"),
    ):
        session.execute(
            text("INSERT INTO app.rooms (tenant_id, location_id, name) VALUES (:t, :l, 'X')"),
            {"t": other_tenant, "l": location["id"]},
        )
