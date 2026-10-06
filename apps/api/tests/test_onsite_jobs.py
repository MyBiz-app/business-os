"""On-site jobs (#42): addresses, travel time, a technician's day and the job's status."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, add_member
from tests.test_appointments import EVERY_DAY, at, barber, local_times  # noqa: F401
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code


@pytest.fixture
def ac(client: TestClient, barber: dict) -> dict:  # noqa: F811
    """An air-conditioning service at the client's home: 60 minutes, 30 minutes to get there."""
    headers = barber["headers"]
    service = client.post(
        "/services",
        json={
            "name": "AC service",
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "on_site": True,
            "travel_minutes": 30,
            "price_amount": 25000,
        },
        headers=headers,
    )
    assert service.status_code == 201, service.text
    assert service.json()["on_site"] is True and service.json()["travel_minutes"] == 30
    dana = new_client(client, headers, "Dana")
    home = client.post(
        f"/clients/{dana}/addresses",
        json={
            "label": "Home",
            "street": "Herzl 10",
            "city": "Tel Aviv",
            "details": "Floor 3",
            "notes": "Gate code 1234",
        },
        headers=headers,
    )
    assert home.status_code == 201, home.text
    return {**barber, "service": service.json(), "dana": dana, "home": home.json()}


def job(ac: dict, hhmm: str, **extra) -> dict:
    return {
        "service_id": ac["service"]["id"],
        "staff_user_id": str(ac["owner"]),
        "starts_at": at(ac["day"], hhmm),
        "client_id": ac["dana"],
        "address_id": ac["home"]["id"],
        **extra,
    }


def test_on_site_only_for_appointments(client: TestClient, barber: dict) -> None:  # noqa: F811
    refused = client.post(
        "/services",
        json={"name": "Class", "duration_minutes": 60, "capacity": 10, "on_site": True},
        headers=barber["headers"],
    )
    assert refused.status_code == 422


def test_travel_time_comes_before_each_job(client: TestClient, ac: dict) -> None:
    headers = ac["headers"]
    params = {"service_id": ac["service"]["id"], "date": ac["day"].isoformat()}

    # Working from 09:00, the first job starts after the 30 minutes on the road.
    slots = local_times(client.get("/appointments/slots", params=params, headers=headers).json())
    assert slots[0] == "09:30" and slots[-1] == "16:00"

    first = client.post("/appointments", json=job(ac, "10:00"), headers=headers)
    assert first.status_code == 201, first.text
    # Busy 09:30-11:00; the next job needs 30 minutes on the road after 11:00.
    taken = client.post("/appointments", json=job(ac, "11:15"), headers=headers)
    assert taken.status_code == 409 and taken.json()["detail"] == "slot_taken"
    early = client.post("/appointments", json=job(ac, "09:15"), headers=headers)
    assert early.status_code == 409 and early.json()["detail"] == "outside_hours"
    after = local_times(client.get("/appointments/slots", params=params, headers=headers).json())
    assert "11:15" not in after and "11:30" in after
    assert "09:30" not in after  # would end at 10:30, inside the first job

    second = client.post("/appointments", json=job(ac, "11:30"), headers=headers)
    assert second.status_code == 201, second.text
    [listed, _] = client.get(
        "/sessions", params={"start": ac["day"].isoformat(), "days": 1}, headers=headers
    ).json()
    assert listed["address"] == "Herzl 10, Floor 3, Tel Aviv"
    assert listed["address_notes"] == "Gate code 1234"
    assert listed["job_status"] == "scheduled" and listed["travel_minutes"] == 30


def test_a_job_needs_an_address_of_its_client(client: TestClient, ac: dict) -> None:
    headers = ac["headers"]
    missing = client.post("/appointments", json=job(ac, "10:00", address_id=None), headers=headers)
    assert missing.status_code == 422 and missing.json()["detail"] == "address_required"
    noa = new_client(client, headers, "Noa")
    elsewhere = client.post("/appointments", json=job(ac, "10:00", client_id=noa), headers=headers)
    assert elsewhere.status_code == 422


def test_technician_moves_the_job_and_done_checks_in(
    client: TestClient, ac: dict, auth: AuthHeaders, engine
) -> None:
    headers = ac["headers"]
    booked = client.post("/appointments", json=job(ac, "10:00"), headers=headers).json()
    session_id = booked["session_id"]

    mine = client.get("/jobs", params={"date": ac["day"].isoformat()}, headers=headers).json()
    assert [j["client_name"] for j in mine] == ["Dana"]
    assert mine[0]["address"].startswith("Herzl 10")

    skipped = client.post(f"/jobs/{session_id}/status", json={"status": "done"}, headers=headers)
    assert skipped.status_code == 409
    for step in ("on_the_way", "in_progress", "done"):
        moved = client.post(f"/jobs/{session_id}/status", json={"status": step}, headers=headers)
        assert moved.status_code == 200, moved.text
        assert moved.json()["job_status"] == step
    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert roster[0]["status"] == "checked_in"
    undone = client.post(
        f"/jobs/{session_id}/status", json={"status": "in_progress"}, headers=headers
    )
    assert undone.status_code == 200
    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert roster[0]["status"] == "booked"

    # Another technician's day is their own; the whole team's day is there too.
    other = uuid4()
    add_member(engine, ac["tenant_id"], other, "staff")
    other_headers = auth(other, ac["tenant_id"])
    day = {"date": ac["day"].isoformat()}
    assert client.get("/jobs", params=day, headers=other_headers).json() == []
    everyone = client.get("/jobs", params={**day, "everyone": True}, headers=other_headers)
    assert [j["session_id"] for j in everyone.json()] == [session_id]


def test_client_books_a_job_at_home_and_sees_its_status(
    client: TestClient, ac: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, ac))
    headers = auth(user, ac["tenant_id"])
    client.patch(
        "/tenants/current", json={"requires_health_declaration": False}, headers=ac["headers"]
    )
    home = client.post(
        "/client/addresses", json={"street": "Ben Yehuda 5", "city": "Haifa"}, headers=headers
    )
    assert home.status_code == 201, home.text
    assert [a["street"] for a in client.get("/client/addresses", headers=headers).json()] == [
        "Ben Yehuda 5"
    ]

    someone_elses = client.post(
        "/client/appointments",
        json={
            "service_id": ac["service"]["id"],
            "staff_user_id": str(ac["owner"]),
            "starts_at": at(ac["day"], "10:00"),
            "address_id": ac["home"]["id"],
        },
        headers=headers,
    )
    assert someone_elses.status_code == 422
    booked = client.post(
        "/client/appointments",
        json={
            "service_id": ac["service"]["id"],
            "staff_user_id": str(ac["owner"]),
            "starts_at": at(ac["day"], "10:00"),
            "address_id": home.json()["id"],
        },
        headers=headers,
    )
    assert booked.status_code == 201, booked.text
    assert booked.json()["address"] == "Ben Yehuda 5, Haifa"
    assert booked.json()["job_status"] == "scheduled"

    client.post(
        f"/jobs/{booked.json()['id']}/status", json={"status": "on_the_way"}, headers=ac["headers"]
    )
    mine = client.get(
        "/client/sessions", params={"start": ac["day"].isoformat(), "days": 1}, headers=headers
    ).json()
    assert [s["job_status"] for s in mine] == ["on_the_way"]
    assert joined["client_id"]


def test_addresses_are_private(client: TestClient, ac: dict, auth: AuthHeaders) -> None:
    alice = uuid4()
    join(client, auth, alice, join_code(client, ac))
    alice_headers = auth(alice, ac["tenant_id"])
    assert client.get("/client/addresses", headers=alice_headers).json() == []
    hijack = client.patch(
        f"/client/addresses/{ac['home']['id']}", json={"city": "X"}, headers=alice_headers
    )
    assert hijack.status_code == 404
