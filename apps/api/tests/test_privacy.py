from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import book, new_session
from tests.test_client_app import give_plan, join, join_code, sign_health


def app_member(client: TestClient, auth: AuthHeaders, studio: dict) -> tuple[dict, dict]:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    client.patch(
        f"/clients/{joined['client_id']}",
        json={
            "phone": "050-1234567",
            "notes": "Knee surgery in 2024",
            "date_of_birth": "1990-03-14",
        },
        headers=studio["headers"],
    )
    give_plan(client, studio, joined["client_id"])
    headers = auth(user, studio["tenant_id"])
    sign_health(client, headers, yes=("bone_joint",))
    return joined, headers


def test_export_has_everything_about_the_client(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    joined, _ = app_member(client, auth, studio)
    book(client, studio["headers"], new_session(client, studio), joined["client_id"])

    response = client.get(f"/clients/{joined['client_id']}/export", headers=studio["headers"])

    assert response.status_code == 200, response.text
    document = response.json()
    assert document["business"] == "Studio Flow"
    assert document["client"]["phone"] == "050-1234567"
    assert document["client"]["uses_client_app"] is True
    assert len(document["bookings"]) == 1 and document["bookings"][0]["service"] == "Pilates"
    assert len(document["plans"]) == 1 and len(document["payments"]) == 1
    [declaration] = document["health_declarations"]
    assert declaration["status"] == "needs_review"
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM app.audit_log WHERE action = 'clients.export'")
            ).scalar_one()
            == 1
        )


def test_erase_clears_personal_data_and_keeps_records(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    joined, member_headers = app_member(client, auth, studio)
    client_id = joined["client_id"]
    full = new_session(client, studio, capacity=1)
    book(client, studio["headers"], full, client_id)
    waiting = client.post("/clients", json={"first_name": "Noa"}, headers=studio["headers"]).json()
    book(client, studio["headers"], full, waiting["id"])  # on the waitlist

    erased = client.post(
        f"/clients/{client_id}/erase", json={"confirm": True}, headers=studio["headers"]
    )

    assert erased.status_code == 200, erased.text
    assert erased.json() == {"cancelled_bookings": 1, "removed_health_declarations": 1}
    profile = client.get(f"/clients/{client_id}", headers=studio["headers"]).json()
    assert profile["first_name"] == "לקוח/ה שנמחק/ה"  # the business's language (he)
    assert profile["erased_at"] is not None and profile["status"] == "inactive"
    assert [profile[k] for k in ("last_name", "email", "phone", "notes", "date_of_birth")] == [
        None, None, None, None, None,
    ]  # fmt: skip
    roster = client.get(f"/sessions/{full}/bookings", headers=studio["headers"]).json()
    noa = next(b for b in roster if b["client_id"] == waiting["id"])
    assert noa["status"] == "booked"  # promoted into the freed spot
    entitlements = client.get(f"/clients/{client_id}/entitlements", headers=studio["headers"])
    assert len(entitlements.json()) == 1  # sales history is kept
    # The client app account is unlinked from the business.
    assert client.get("/client/bookings", headers=member_headers).status_code == 403


def test_erased_client_gets_nothing_new(client: TestClient, studio: dict) -> None:
    created = client.post(
        "/clients",
        json={"first_name": "Dana", "email": "dana@example.com"},
        headers=studio["headers"],
    ).json()
    client.post(
        f"/clients/{created['id']}/erase", json={"confirm": True}, headers=studio["headers"]
    )

    edit = client.patch(
        f"/clients/{created['id']}", json={"first_name": "Dana"}, headers=studio["headers"]
    )
    booking = client.post(
        f"/sessions/{new_session(client, studio)}/bookings",
        json={"client_id": created["id"]},
        headers=studio["headers"],
    )
    again = client.post(
        f"/clients/{created['id']}/erase", json={"confirm": True}, headers=studio["headers"]
    )
    recreated = client.post(
        "/clients",
        json={"first_name": "Dana", "email": "dana@example.com"},
        headers=studio["headers"],
    )

    assert edit.json()["detail"] == "client_erased"
    assert booking.json()["detail"] == "client_erased"
    assert again.json()["detail"] == "already_erased"
    assert recreated.status_code == 201  # the email is free again


def test_privacy_requests_are_for_owners_only(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    created = client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"]).json()
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    manager_headers = auth(manager, studio["tenant_id"])

    assert (
        client.get(f"/clients/{created['id']}/export", headers=manager_headers).status_code == 403
    )
    erase = client.post(
        f"/clients/{created['id']}/erase", json={"confirm": True}, headers=manager_headers
    )
    assert erase.status_code == 403
    unconfirmed = client.post(
        f"/clients/{created['id']}/erase", json={"confirm": False}, headers=studio["headers"]
    )
    assert unconfirmed.status_code == 422


def test_privacy_covers_the_clients_lead(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"crm": 1}}, headers=headers)
    lead = client.post(
        "/leads", json={"first_name": "Gal", "phone": "050-3333333"}, headers=headers
    ).json()
    client.post(
        f"/leads/{lead['id']}/activities", json={"kind": "call", "note": "Wants evenings"},
        headers=headers,
    )  # fmt: skip
    client_id = client.post(f"/leads/{lead['id']}/convert", headers=headers).json()["client_id"]

    document = client.get(f"/clients/{client_id}/export", headers=headers).json()
    [exported] = document["leads"]
    assert exported["phone"] == "050-3333333"
    assert "Wants evenings" in [a["note"] for a in exported["activities"]]

    client.post(f"/clients/{client_id}/erase", json={"confirm": True}, headers=headers)
    assert client.get(f"/leads/{lead['id']}", headers=headers).status_code == 404


def test_privacy_covers_addresses_dependents_documents_and_quotes(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from tests.test_documents_time import upload
    from tests.test_quotes import new_quote

    headers = studio["headers"]
    dana = client.post("/clients", json={"first_name": "Dana"}, headers=headers).json()["id"]
    address = client.post(
        f"/clients/{dana}/addresses",
        json={"street": "Herzl 1", "city": "Tel Aviv", "details": "Floor 3"},
        headers=headers,
    )
    assert address.status_code == 201, address.text
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.dependents (tenant_id, client_id, kind, name)
                VALUES (:t, :c, 'child', 'Noa')
            """),
            {"t": studio["tenant_id"], "c": dana},
        )
    upload(client, headers, dana, "contract.pdf")
    quote = new_quote(client, headers, dana)
    client.post(f"/quotes/{quote['id']}/send", headers=headers)
    client.post(f"/public/quotes/{quote['token']}/answer", json={"accept": True, "name": "Dana L"})

    exported = client.get(f"/clients/{dana}/export", headers=headers).json()
    assert exported["addresses"][0]["street"] == "Herzl 1"
    assert exported["dependents"][0]["name"] == "Noa"
    assert exported["documents"][0]["name"] == "contract.pdf"
    assert exported["quotes"][0]["accepted_name"] == "Dana L"

    erased = client.post(f"/clients/{dana}/erase", json={"confirm": True}, headers=headers)
    assert erased.status_code == 200, erased.text
    after = client.get(f"/clients/{dana}/export", headers=headers).json()
    assert after["addresses"] == [] and after["dependents"] == [] and after["documents"] == []
    [kept] = after["quotes"]  # a commercial record stays, without the name typed to accept it
    assert kept["status"] == "accepted" and kept["accepted_name"] != "Dana L"
