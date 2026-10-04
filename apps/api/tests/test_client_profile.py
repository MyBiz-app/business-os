from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import book, new_client, new_session

GARAGE = {"name": "Moti Garage", "vertical": "garage", "locale": "en",
          "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip


def test_fields_come_from_the_vertical_pack(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    tenant_id = client.post("/tenants", json=GARAGE, headers=auth(owner)).json()["id"]
    headers = auth(owner, tenant_id)
    fields = client.get("/clients/fields", headers=headers).json()
    assert [f["key"] for f in fields][:3] == ["plate", "make", "model"]

    created = client.post(
        "/clients",
        json={
            "first_name": "Avi",
            "custom_fields": {"plate": " 12-345-67 ", "year": "2019", "make": ""},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["custom_fields"] == {"plate": "12-345-67", "year": 2019}

    updated = client.patch(
        f"/clients/{created.json()['id']}",
        json={"custom_fields": {"plate": "12-345-67", "next_inspection": "2027-03-01"}},
        headers=headers,
    ).json()
    assert updated["custom_fields"] == {"plate": "12-345-67", "next_inspection": "2027-03-01"}

    for bad in ({"color": "red"}, {"year": "old"}, {"next_inspection": "soon"}):
        response = client.patch(
            f"/clients/{created.json()['id']}", json={"custom_fields": bad}, headers=headers
        )
        assert response.status_code == 422, bad


def test_select_options_are_checked(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    ok = client.post(
        "/clients", json={"first_name": "Noa", "custom_fields": {"goal": "strength"}},
        headers=headers,
    )  # fmt: skip
    bad = client.post(
        "/clients", json={"first_name": "Noa", "custom_fields": {"goal": "fame"}},
        headers=headers,
    )  # fmt: skip
    assert ok.status_code == 201 and bad.status_code == 422


def test_visit_notes(client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine) -> None:
    headers = studio["headers"]
    client_id = new_client(client, headers, "Noa")
    session_id = new_session(client, studio)
    booking = book(client, headers, session_id, client_id).json()

    # An instructor (staff: bookings.manage, no clients.write) logs what happened.
    coach = auth(studio["coach"], studio["tenant_id"])
    note = client.post(
        f"/clients/{client_id}/notes",
        json={"body": "  Worked on posture  ", "booking_id": booking["id"]},
        headers=coach,
    )
    assert note.status_code == 201, note.text
    assert note.json()["body"] == "Worked on posture"
    assert note.json()["service_name"] == "Pilates"
    client.post(f"/clients/{client_id}/notes", json={"body": "Owner note"}, headers=headers)

    notes = client.get(f"/clients/{client_id}/notes", headers=coach).json()
    assert [n["body"] for n in notes] == ["Owner note", "Worked on posture"]

    # The coach can delete their own note, not the owner's.
    own, other = notes[1]["id"], notes[0]["id"]
    assert client.delete(f"/clients/{client_id}/notes/{other}", headers=coach).status_code == 403
    assert client.delete(f"/clients/{client_id}/notes/{own}", headers=coach).status_code == 204

    # A booking of another client is refused; read-only staff can't write.
    other_client = new_client(client, headers, "Dana")
    wrong = client.post(
        f"/clients/{other_client}/notes",
        json={"body": "x", "booking_id": booking["id"]},
        headers=headers,
    )
    assert wrong.status_code == 422
    viewer = uuid4()
    add_member(engine, studio["tenant_id"], viewer, "staff")
    role = client.post(
        "/roles", json={"name": "Viewer", "permissions": ["clients.read"]}, headers=headers
    ).json()
    client.patch(f"/staff/{viewer}", json={"custom_role_id": role["id"]}, headers=headers)
    viewer_headers = auth(viewer, studio["tenant_id"])
    assert client.get(f"/clients/{client_id}/notes", headers=viewer_headers).status_code == 200
    refused = client.post(f"/clients/{client_id}/notes", json={"body": "x"}, headers=viewer_headers)
    assert refused.status_code == 403


def test_privacy_covers_profile_and_notes(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    client_id = client.post(
        "/clients",
        json={"first_name": "Gil", "custom_fields": {"injuries": "Left knee"}},
        headers=headers,
    ).json()["id"]
    client.post(f"/clients/{client_id}/notes", json={"body": "Knee better"}, headers=headers)

    document = client.get(f"/clients/{client_id}/export", headers=headers).json()
    assert document["client"]["custom_fields"] == {"injuries": "Left knee"}
    assert [n["body"] for n in document["visit_notes"]] == ["Knee better"]

    client.post(f"/clients/{client_id}/erase", json={"confirm": True}, headers=headers)
    assert client.get(f"/clients/{client_id}", headers=headers).json()["custom_fields"] == {}
    assert client.get(f"/clients/{client_id}/notes", headers=headers).json() == []
