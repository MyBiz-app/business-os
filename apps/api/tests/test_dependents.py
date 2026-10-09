"""Dependents (#43): the pets or children a client brings."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.catalog.verticals import CATALOG, ClientField
from tests.conftest import STUDIO, AuthHeaders
from tests.test_bookings import book, new_client, new_session
from tests.test_client_app import member, upcoming

PET_FIELDS = (
    ClientField(key="species", kind="select", options=("dog", "cat")),
    ClientField(key="weight_kg", kind="number"),
)


@pytest.fixture
def pets(monkeypatch: pytest.MonkeyPatch, studio: dict) -> dict:
    """The studio's industry pack (fitness) keeps pets for these tests."""
    pack = replace(CATALOG["fitness"], dependents="pet", dependent_fields=PET_FIELDS)
    monkeypatch.setitem(CATALOG, "fitness", pack)
    return studio


def add(client: TestClient, headers: dict, client_id: str, name: str, **body) -> dict:
    created = client.post(
        f"/clients/{client_id}/dependents", json={"name": name, **body}, headers=headers
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_staff_manage_dependents_with_pack_fields(client: TestClient, pets: dict) -> None:
    headers = pets["headers"]
    owner = new_client(client, headers, "Dana")
    settings = client.get("/dependents/settings", headers=headers).json()
    assert settings["kind"] == "pet" and settings["required"] is False
    assert [f["key"] for f in settings["fields"]] == ["species", "weight_kg"]

    rex = add(client, headers, owner, " Rex ", details={"species": "dog", "weight_kg": "12"})
    assert rex["kind"] == "pet" and rex["name"] == "Rex"
    assert rex["details"] == {"species": "dog", "weight_kg": 12}
    add(client, headers, owner, "Mitzi", details={"species": "cat"}, notes="Shy")

    unknown = client.post(
        f"/clients/{owner}/dependents",
        json={"name": "Bob", "details": {"color": "red"}},
        headers=headers,
    )
    assert unknown.status_code == 422
    bad_option = client.post(
        f"/clients/{owner}/dependents",
        json={"name": "Bob", "details": {"species": "horse"}},
        headers=headers,
    )
    assert bad_option.status_code == 422

    retired = client.patch(f"/dependents/{rex['id']}", json={"active": False}, headers=headers)
    assert retired.status_code == 200 and retired.json()["active"] is False
    listed = client.get(f"/clients/{owner}/dependents", headers=headers).json()
    assert [d["name"] for d in listed] == ["Mitzi", "Rex"]  # active first


def test_industries_without_dependents_refuse_them(client: TestClient, studio: dict) -> None:
    settings = client.get("/dependents/settings", headers=studio["headers"]).json()
    assert settings == {"kind": None, "required": False, "fields": []}
    owner = new_client(client, studio["headers"], "Dana")
    refused = client.post(
        f"/clients/{owner}/dependents", json={"name": "Rex"}, headers=studio["headers"]
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "dependents_off"


def test_two_dogs_of_one_owner_in_the_same_session(client: TestClient, pets: dict) -> None:
    headers = pets["headers"]
    owner = new_client(client, headers, "Dana")
    rex, luna = (add(client, headers, owner, name) for name in ("Rex", "Luna"))
    session_id = new_session(client, pets, capacity=3)

    first = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": owner, "dependent_id": rex["id"]},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["dependent_name"] == "Rex"
    second = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": owner, "dependent_id": luna["id"]},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    again = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": owner, "dependent_id": rex["id"]},
        headers=headers,
    )
    assert again.status_code == 409 and again.json()["detail"] == "already_booked"

    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert sorted(b["dependent_name"] for b in roster) == ["Luna", "Rex"]
    history = client.get(f"/clients/{owner}/bookings", headers=headers).json()
    assert sorted(b["dependent_name"] for b in history) == ["Luna", "Rex"]


def test_a_booking_names_only_the_clients_own_active_dependent(
    client: TestClient, pets: dict
) -> None:
    headers = pets["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    rex = add(client, headers, dana, "Rex")
    session_id = new_session(client, pets)

    someone_elses = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": noa, "dependent_id": rex["id"]},
        headers=headers,
    )
    assert someone_elses.status_code == 422
    assert someone_elses.json()["detail"] == "unknown_dependent"

    client.patch(f"/dependents/{rex['id']}", json={"active": False}, headers=headers)
    retired = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": dana, "dependent_id": rex["id"]},
        headers=headers,
    )
    assert retired.status_code == 422


def test_packs_can_require_a_dependent(
    client: TestClient, pets: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(CATALOG, "fitness", replace(CATALOG["fitness"], dependent_required=True))
    headers = pets["headers"]
    owner = new_client(client, headers, "Dana")
    session_id = new_session(client, pets)

    missing = book(client, headers, session_id, owner)
    assert missing.status_code == 422 and missing.json()["detail"] == "dependent_required"


def test_client_adds_pets_and_books_for_each(
    client: TestClient, pets: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    member(client, auth, pets, user)
    headers = auth(user, pets["tenant_id"])
    session_id = new_session(client, pets, capacity=3)

    settings = client.get("/client/dependents/settings", headers=headers).json()
    assert settings["kind"] == "pet"
    [business] = client.get("/client/businesses", headers=headers).json()
    assert business["dependents"] == "pet" and business["dependent_required"] is False
    rex = client.post(
        "/client/dependents", json={"name": "Rex", "details": {"species": "dog"}}, headers=headers
    )
    assert rex.status_code == 201, rex.text
    luna = client.post("/client/dependents", json={"name": "Luna"}, headers=headers).json()
    renamed = client.patch(
        f"/client/dependents/{luna['id']}", json={"name": "Luna Belle"}, headers=headers
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Luna Belle"
    assert len(client.get("/client/dependents", headers=headers).json()) == 2

    for dependent in (rex.json(), luna):
        booked = client.post(
            f"/client/sessions/{session_id}/bookings",
            json={"dependent_id": dependent["id"]},
            headers=headers,
        )
        assert booked.status_code == 201, booked.text

    [listed] = upcoming(client, headers)
    assert listed["spots_left"] == 1
    assert [b["dependent_name"] for b in listed["my_bookings"]] == ["Rex", "Luna Belle"]
    assert listed["my_booking"]["dependent_name"] == "Rex"
    mine = client.get("/client/bookings", headers=headers).json()
    assert sorted(b["dependent_name"] for b in mine) == ["Luna Belle", "Rex"]


def test_clients_see_only_their_own_dependents(
    client: TestClient, pets: dict, auth: AuthHeaders
) -> None:
    alice, bob = uuid4(), uuid4()
    member(client, auth, pets, alice)
    member(client, auth, pets, bob)
    alice_headers, bob_headers = (auth(u, pets["tenant_id"]) for u in (alice, bob))
    rex = client.post("/client/dependents", json={"name": "Rex"}, headers=alice_headers).json()

    assert client.get("/client/dependents", headers=bob_headers).json() == []
    hijack = client.patch(
        f"/client/dependents/{rex['id']}", json={"name": "Mine"}, headers=bob_headers
    )
    assert hijack.status_code == 404
    session_id = new_session(client, pets)
    borrowed = client.post(
        f"/client/sessions/{session_id}/bookings",
        json={"dependent_id": rex["id"]},
        headers=bob_headers,
    )
    assert borrowed.status_code == 422


def test_other_businesses_cannot_see_dependents(
    client: TestClient, pets: dict, auth: AuthHeaders
) -> None:
    owner = new_client(client, pets["headers"], "Dana")
    rex = add(client, pets["headers"], owner, "Rex")
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={**STUDIO, "name": "Other"},
        headers=auth(other_owner),
    ).json()
    other_headers = auth(other_owner, other["id"])

    assert client.get(f"/clients/{owner}/dependents", headers=other_headers).json() == []
    patched = client.patch(f"/dependents/{rex['id']}", json={"name": "X"}, headers=other_headers)
    assert patched.status_code == 404
    planted = client.post(
        f"/clients/{owner}/dependents", json={"name": "Spy"}, headers=other_headers
    )
    assert planted.status_code == 404
