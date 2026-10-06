"""Resources (#41): courts and rooms reserved by the hour."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api.resources import price_of
from tests.conftest import AuthHeaders, local_today
from tests.test_appointments import at, local_times
from tests.test_bookings import new_client, set_status
from tests.test_client_app import join, join_code

OPEN = [{"weekday": d, "starts": "08:00", "ends": "22:00"} for d in range(7)]


@pytest.fixture
def club(client: TestClient, studio: dict) -> dict:
    """Two padel courts open 08:00-22:00, rented by 60 to 120 minutes at ₪120 an hour."""
    headers, location = studio["headers"], studio["location"]
    courts = [
        client.post(
            f"/locations/{location['id']}/rooms",
            json={"name": name, "capacity": 4, "bookable": True},
            headers=headers,
        ).json()
        for name in ("Court 1", "Court 2")
    ]
    for court in courts:
        hours = client.put(f"/rooms/{court['id']}/hours", json=OPEN, headers=headers)
        assert hours.status_code == 200, hours.text
    padel = client.post(
        "/services",
        json={
            "name": "Padel court",
            "duration_minutes": 60,
            "booking_mode": "resource",
            "min_minutes": 60,
            "max_minutes": 120,
            "step_minutes": 30,
            "price_per_hour": 12000,
        },
        headers=headers,
    )
    assert padel.status_code == 201, padel.text
    rooms = client.put(
        f"/services/{padel.json()['id']}/rooms", json=[c["id"] for c in courts], headers=headers
    )
    assert rooms.status_code == 200, rooms.text
    return {
        **studio,
        "courts": courts,
        "padel": padel.json(),
        "day": local_today() + timedelta(days=2),
    }


def params(club: dict, minutes: int, **extra) -> dict:
    return {
        "service_id": club["padel"]["id"],
        "date": club["day"].isoformat(),
        "minutes": minutes,
        **extra,
    }


def reservation(club: dict, court: int, hhmm: str, minutes: int, client_id: str) -> dict:
    return {
        "service_id": club["padel"]["id"],
        "room_id": club["courts"][court]["id"],
        "starts_at": at(club["day"], hhmm),
        "minutes": minutes,
        "client_id": client_id,
    }


def test_price_per_hour_rounds_to_minor_units() -> None:
    assert price_of(12000, 60) == 12000
    assert price_of(12000, 90) == 18000
    assert price_of(9999, 45) == 7499  # 7499.25


def test_a_resource_needs_its_lengths_and_price(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    base = {"name": "Court", "duration_minutes": 60, "booking_mode": "resource"}
    missing = client.post("/services", json=base, headers=headers)
    uneven = client.post(
        "/services",
        json={
            **base,
            "min_minutes": 60,
            "max_minutes": 100,
            "step_minutes": 30,
            "price_per_hour": 100,
        },
        headers=headers,
    )
    # A class can't become a resource without them either (the database says no).
    switched = client.patch(
        f"/services/{studio['service']['id']}", json={"booking_mode": "resource"}, headers=headers
    )
    assert missing.status_code == 422 and uneven.status_code == 422
    assert switched.status_code == 422 and switched.json()["detail"] == "invalid_resource"


def test_only_bookable_rooms_serve_a_resource(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    refused = client.put(
        f"/services/{club['padel']['id']}/rooms", json=[club["room"]["id"]], headers=headers
    )
    not_resource = client.put(
        f"/services/{club['service']['id']}/rooms", json=[club["courts"][0]["id"]], headers=headers
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "room_not_bookable"
    assert not_resource.status_code == 409
    [listed] = client.get("/resources", headers=headers).json()
    assert [r["name"] for r in listed["rooms"]] == ["Court 1", "Court 2"]
    assert (listed["min_minutes"], listed["max_minutes"], listed["step_minutes"]) == (60, 120, 30)


def test_free_times_per_court_and_length(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    hour = client.get("/resources/slots", params=params(club, 60), headers=headers).json()
    two = client.get("/resources/slots", params=params(club, 120), headers=headers).json()
    odd = client.get("/resources/slots", params=params(club, 75), headers=headers)

    first_court = [s for s in hour if s["room_name"] == "Court 1"]
    assert local_times(first_court)[:2] == ["08:00", "08:15"]
    assert local_times(first_court)[-1] == "21:00"
    assert local_times([s for s in two if s["room_name"] == "Court 1"])[-1] == "20:00"
    assert {s["price_amount"] for s in hour} == {12000} and {s["price_amount"] for s in two} == {
        24000
    }
    assert odd.status_code == 422 and odd.json()["detail"] == "length_not_offered"


def test_reserve_price_and_no_double_booking(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")

    made = client.post(
        "/resources/reservations", json=reservation(club, 0, "18:00", 90, dana), headers=headers
    )
    overlap = client.post(
        "/resources/reservations", json=reservation(club, 0, "19:00", 60, noa), headers=headers
    )
    other_court = client.post(
        "/resources/reservations", json=reservation(club, 1, "19:00", 60, noa), headers=headers
    )
    late = client.post(
        "/resources/reservations", json=reservation(club, 1, "21:30", 60, noa), headers=headers
    )

    assert made.status_code == 201, made.text
    assert made.json()["status"] == "booked" and made.json()["plan_name"] is None
    assert overlap.status_code == 409 and overlap.json()["detail"] == "slot_taken"
    assert other_court.status_code == 201
    assert late.status_code == 409 and late.json()["detail"] == "outside_hours"
    sessions = client.get(
        "/sessions", params={"start": club["day"].isoformat(), "days": 1}, headers=headers
    ).json()
    mine = next(s for s in sessions if s["appointment_client"] == "Dana")
    assert mine["booking_mode"] == "resource" and mine["room_name"] == "Court 1"
    assert (mine["price_amount"], mine["price_currency"]) == (18000, "ILS")
    free = local_times(
        [
            s
            for s in client.get("/resources/slots", params=params(club, 60), headers=headers).json()
            if s["room_name"] == "Court 1"
        ]
    )
    assert "17:00" in free and "17:15" not in free and "19:30" in free and "18:00" not in free


def test_a_class_in_the_room_blocks_it(client: TestClient, club: dict) -> None:
    headers, court = club["headers"], club["courts"][0]
    clinic = client.post(
        "/sessions",
        json={
            "service_id": club["service"]["id"],
            "location_id": club["location"]["id"],
            "room_id": court["id"],
            "date": club["day"].isoformat(),
            "start_time": "10:00",
            "duration_minutes": 55,
            "capacity": 4,
        },
        headers=headers,
    )
    assert clinic.status_code == 201, clinic.text
    dana = new_client(client, headers, "Dana")
    blocked = client.post(
        "/resources/reservations", json=reservation(club, 0, "10:30", 60, dana), headers=headers
    )
    assert blocked.status_code == 409 and blocked.json()["detail"] == "slot_taken"


def test_cancelling_frees_the_court(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    made = client.post(
        "/resources/reservations", json=reservation(club, 0, "18:00", 60, dana), headers=headers
    ).json()
    assert set_status(client, headers, made["id"], "cancelled").status_code == 200
    again = client.post(
        "/resources/reservations", json=reservation(club, 0, "18:00", 60, noa), headers=headers
    )
    assert again.status_code == 201, again.text


def test_two_at_once_get_one_court(client: TestClient, club: dict, engine: Engine) -> None:
    """Pressing "book" at the same moment: exactly one wins, the database guarantees it."""
    headers = club["headers"]
    people = [new_client(client, headers, f"Player {i}") for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda person: (
                    client.post(
                        "/resources/reservations",
                        json=reservation(club, 0, "12:00", 60, person),
                        headers=headers,
                    ).status_code
                ),
                people,
            )
        )
    assert sorted(results) == [201, 409, 409, 409, 409, 409]
    with engine.connect() as connection:
        held = connection.execute(
            text("SELECT count(*) FROM app.sessions WHERE reserved AND status = 'scheduled'")
        ).scalar_one()
    assert held == 1


def test_clients_reserve_in_the_app_without_a_plan(
    client: TestClient, club: dict, auth: AuthHeaders
) -> None:
    # A club asks no health declaration (the studio fixture's fitness pack does).
    client.patch(
        "/tenants/current", json={"requires_health_declaration": False}, headers=club["headers"]
    )
    user = uuid4()
    join(client, auth, user, join_code(client, club))
    me = auth(user, club["tenant_id"])

    [service] = client.get("/client/resources", headers=me).json()
    slots = client.get("/client/resources/slots", params=params(club, 90), headers=me).json()
    body = {
        "service_id": service["id"],
        "room_id": slots[0]["room_id"],
        "starts_at": slots[0]["starts_at"],
        "minutes": 90,
    }
    made = client.post("/client/resources/reservations", json=body, headers=me)
    taken = client.post("/client/resources/reservations", json=body, headers=me)
    # A reservation isn't a class: it can't be joined like one.
    assert made.status_code == 201, made.text
    joined = client.post(f"/client/sessions/{made.json()['id']}/bookings", headers=me)

    assert len(service["rooms"]) == 2
    assert made.status_code == 201, made.text
    assert made.json()["my_booking"]["status"] == "booked"
    assert taken.status_code == 409
    assert joined.status_code == 409
    cancelled = client.post(
        f"/client/bookings/{made.json()['my_booking']['id']}/cancel", headers=me
    )
    assert cancelled.status_code == 200, cancelled.text
    again = client.get("/client/resources/slots", params=params(club, 90), headers=me).json()
    assert again[0]["starts_at"] == slots[0]["starts_at"]


def test_other_businesses_see_nothing(client: TestClient, club: dict, auth: AuthHeaders) -> None:
    other = uuid4()
    business = {
        "name": "Other",
        "vertical": "fitness",
        "locale": "en",
        "time_zone": "Asia/Jerusalem",
        "currency": "ILS",
    }
    tenant_id = client.post("/tenants", json=business, headers=auth(other)).json()["id"]
    theirs = auth(other, tenant_id)
    court = club["courts"][0]["id"]
    assert client.get("/resources", headers=theirs).json() == []
    assert client.get(f"/rooms/{court}/hours", headers=theirs).status_code == 404
    assert client.put(f"/rooms/{court}/hours", json=OPEN, headers=theirs).status_code == 404
    dana = new_client(client, theirs, "Dana")
    stolen = client.post(
        "/resources/reservations", json=reservation(club, 0, "09:00", 60, dana), headers=theirs
    )
    assert stolen.status_code == 404
