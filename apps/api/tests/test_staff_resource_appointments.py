"""A private lesson takes a staff member and a room together (slice C4, model M5)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, local_today
from tests.test_appointments import at, local_times
from tests.test_bookings import new_client, set_status
from tests.test_client_app import join, join_code

STAFF_HOURS = [{"weekday": d, "starts": "09:00", "ends": "17:00"} for d in range(7)]
COURT_HOURS = [{"weekday": d, "starts": "10:00", "ends": "12:00"} for d in range(7)]


def lesson_service(client: TestClient, headers: dict, **extra) -> dict:
    response = client.post(
        "/services",
        json={
            "name": "Private tennis lesson",
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "needs_resource": True,
            "price_amount": 25000,
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def academy(client: TestClient, studio: dict) -> dict:
    """Two courts open 10:00-12:00, a lesson that needs a coach and a court, two coaches."""
    headers, location = studio["headers"], studio["location"]
    courts = [
        client.post(
            f"/locations/{location['id']}/rooms",
            json={"name": name, "bookable": True},
            headers=headers,
        ).json()
        for name in ("Court 1", "Court 2")
    ]
    for court in courts:
        hours = client.put(f"/rooms/{court['id']}/hours", json=COURT_HOURS, headers=headers)
        assert hours.status_code == 200, hours.text
    lesson = lesson_service(client, headers)
    rooms = client.put(
        f"/services/{lesson['id']}/rooms", json=[c["id"] for c in courts], headers=headers
    )
    assert rooms.status_code == 200, rooms.text
    coaches = [studio["owner"], studio["coach"]]
    for coach in coaches:
        done = client.put(f"/staff/{coach}/hours", json=STAFF_HOURS, headers=headers)
        assert done.status_code == 200, done.text
    return {
        **studio,
        "courts": courts,
        "lesson": lesson,
        "coaches": coaches,
        "day": local_today() + timedelta(days=2),
    }


def book_lesson(client: TestClient, academy: dict, coach: int, hhmm: str, client_id: str, **extra):
    return client.post(
        "/appointments",
        json={
            "service_id": academy["lesson"]["id"],
            "staff_user_id": str(academy["coaches"][coach]),
            "starts_at": at(academy["day"], hhmm),
            "client_id": client_id,
            **extra,
        },
        headers=academy["headers"],
    )


def rooms_held(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as connection:
        return [
            (row.room, row.status)
            for row in connection.execute(
                text("""
                    SELECT r.name AS room, s.status FROM app.sessions s
                    JOIN app.rooms r ON r.id = s.room_id
                    WHERE s.holds_room
                    ORDER BY r.name, s.status
                """)
            )
        ]


def test_only_an_appointment_in_the_business_can_need_a_room(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    for extra in ({"booking_mode": "class"}, {"on_site": True}):
        body = {"name": "Bad", "duration_minutes": 60, "needs_resource": True, **extra}
        assert client.post("/services", json=body, headers=headers).status_code == 422
    pilates = studio["service"]
    changed = client.patch(
        f"/services/{pilates['id']}", json={"needs_resource": True}, headers=headers
    )
    assert changed.status_code == 422 and changed.json()["detail"] == "invalid_needs_resource"
    plain = client.post(
        "/services",
        json={"name": "Plain", "duration_minutes": 30, "booking_mode": "appointment"},
        headers=headers,
    ).json()
    assert plain["needs_resource"] is False


def test_rooms_of_a_lesson(client: TestClient, academy: dict) -> None:
    headers, lesson = academy["headers"], academy["lesson"]
    listed = client.get(f"/services/{lesson['id']}/rooms", headers=headers).json()
    assert [r["name"] for r in listed] == ["Court 1", "Court 2"]
    plain = client.post(
        "/services",
        json={"name": "Plain", "duration_minutes": 30, "booking_mode": "appointment"},
        headers=headers,
    ).json()
    refused = client.put(
        f"/services/{plain['id']}/rooms", json=[academy["courts"][0]["id"]], headers=headers
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "not_a_resource"
    assert client.get(f"/services/{uuid4()}/rooms", headers=headers).status_code == 404


def test_free_times_need_a_coach_and_a_court(client: TestClient, academy: dict) -> None:
    headers = academy["headers"]
    params = {"service_id": academy["lesson"]["id"], "date": academy["day"].isoformat()}
    slots = client.get("/appointments/slots", params=params, headers=headers).json()
    # Coaches work 09:00-17:00 but the courts are open only 10:00-12:00: the last start for a
    # 60-minute lesson is 11:00, and every time names the court it would use.
    assert sorted(set(local_times(slots)))[0] == "10:00"
    assert sorted(set(local_times(slots)))[-1] == "11:00"
    assert {s["room_name"] for s in slots} == {"Court 1"}
    one_court = client.get(
        "/appointments/slots",
        params={**params, "room_id": academy["courts"][1]["id"]},
        headers=headers,
    ).json()
    assert {s["room_name"] for s in one_court} == {"Court 2"}


def test_a_lesson_holds_the_coach_and_a_court(
    client: TestClient, academy: dict, engine: Engine
) -> None:
    headers = academy["headers"]
    dana, noa, yael = (new_client(client, headers, n) for n in ("Dana", "Noa", "Yael"))

    first = book_lesson(client, academy, 0, "10:00", dana)
    assert first.status_code == 201, first.text
    assert rooms_held(engine) == [("Court 1", "scheduled")]  # the first free court

    # The other coach at the same time gets the other court.
    second = book_lesson(client, academy, 1, "10:00", noa)
    assert second.status_code == 201, second.text
    assert rooms_held(engine) == [("Court 1", "scheduled"), ("Court 2", "scheduled")]

    # Both courts are in use, so a third lesson at that time has no court (the coaches are busy).
    full = book_lesson(client, academy, 0, "10:30", yael)
    assert full.status_code == 409 and full.json()["detail"] == "slot_taken"
    params = {"service_id": academy["lesson"]["id"], "date": academy["day"].isoformat()}
    free = client.get("/appointments/slots", params=params, headers=headers).json()
    assert "10:00" not in local_times(free) and "10:30" not in local_times(free)
    assert "11:00" in local_times(free)


def test_a_busy_coach_blocks_the_lesson_even_with_a_free_court(
    client: TestClient, academy: dict
) -> None:
    headers = academy["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    assert book_lesson(client, academy, 0, "10:00", dana).status_code == 201
    same_coach = book_lesson(client, academy, 0, "10:00", noa)
    assert same_coach.status_code == 409 and same_coach.json()["detail"] == "slot_taken"
    # A haircut-style appointment elsewhere would also hold the coach, but a free court at the
    # same time is still free: the other coach can have it.
    other = book_lesson(client, academy, 1, "10:00", noa)
    assert other.status_code == 201, other.text


def test_choosing_a_court_and_the_court_being_taken(client: TestClient, academy: dict) -> None:
    headers = academy["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    court_two = academy["courts"][1]["id"]
    chosen = book_lesson(client, academy, 0, "11:00", dana, room_id=court_two)
    assert chosen.status_code == 201, chosen.text
    taken = book_lesson(client, academy, 1, "11:00", noa, room_id=court_two)
    assert taken.status_code == 409 and taken.json()["detail"] == "slot_taken"
    elsewhere = book_lesson(client, academy, 1, "11:00", noa)  # no court named: Court 1 is free
    assert elsewhere.status_code == 201, elsewhere.text
    not_a_court = book_lesson(client, academy, 1, "10:00", noa, room_id=str(uuid4()))
    assert not_a_court.status_code == 404


def test_the_court_must_be_open(client: TestClient, academy: dict) -> None:
    dana = new_client(client, academy["headers"], "Dana")
    # The coach works at 09:00 but the courts open at 10:00; 11:30 would end after they close.
    early = book_lesson(client, academy, 0, "09:00", dana)
    late = book_lesson(client, academy, 0, "11:30", dana)
    assert early.status_code == 409 and early.json()["detail"] == "outside_hours"
    assert late.status_code == 409 and late.json()["detail"] == "outside_hours"


def test_a_lesson_blocks_a_court_rental_and_the_other_way(
    client: TestClient, academy: dict
) -> None:
    headers = academy["headers"]
    padel = client.post(
        "/services",
        json={
            "name": "Court rental",
            "duration_minutes": 60,
            "booking_mode": "resource",
            "min_minutes": 60,
            "max_minutes": 60,
            "step_minutes": 30,
            "price_per_hour": 12000,
        },
        headers=headers,
    ).json()
    client.put(
        f"/services/{padel['id']}/rooms",
        json=[c["id"] for c in academy["courts"]],
        headers=headers,
    )
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    rental = {
        "service_id": padel["id"],
        "room_id": academy["courts"][0]["id"],
        "starts_at": at(academy["day"], "10:00"),
        "minutes": 60,
        "client_id": noa,
    }

    assert book_lesson(client, academy, 0, "10:00", dana).status_code == 201  # Court 1
    blocked = client.post("/resources/reservations", json=rental, headers=headers)
    assert blocked.status_code == 409 and blocked.json()["detail"] == "slot_taken"

    # The other way round: with Court 1 rented, the lesson takes Court 2.
    rented = client.post(
        "/resources/reservations",
        json={**rental, "starts_at": at(academy["day"], "11:00")},
        headers=headers,
    )
    assert rented.status_code == 201, rented.text
    after = book_lesson(client, academy, 1, "11:00", dana)
    assert after.status_code == 201, after.text


def test_cancelling_frees_the_coach_and_the_court(
    client: TestClient, academy: dict, engine: Engine
) -> None:
    headers = academy["headers"]
    dana, noa = new_client(client, headers, "Dana"), new_client(client, headers, "Noa")
    booked = book_lesson(client, academy, 0, "10:00", dana).json()
    assert set_status(client, headers, booked["id"], "cancelled").status_code == 200
    assert rooms_held(engine) == [("Court 1", "cancelled")]
    again = book_lesson(client, academy, 0, "10:00", noa)
    assert again.status_code == 201, again.text
    assert rooms_held(engine) == [("Court 1", "cancelled"), ("Court 1", "scheduled")]


def test_no_path_books_the_lesson_without_a_court(
    client: TestClient, academy: dict, engine: Engine
) -> None:
    """The database refuses an appointment of a service that needs a room when it holds none."""
    with engine.connect() as connection, pytest.raises(Exception, match="needs a room"):
        connection.execute(
            text("""
                INSERT INTO app.sessions
                    (tenant_id, service_id, instructor_user_id, capacity, starts_at, ends_at)
                VALUES (:t, :s, :u, 1, now() + interval '3 days',
                        now() + interval '3 days 1 hour')
            """),
            {
                "t": academy["tenant_id"],
                "s": academy["lesson"]["id"],
                "u": academy["owner"],
            },
        )


def test_two_at_once_get_one_court_each(client: TestClient, academy: dict, engine: Engine) -> None:
    """Four people book the same 10:00 lesson, two coaches and two courts: exactly two win."""
    headers = academy["headers"]
    people = [new_client(client, headers, f"Player {i}") for i in range(4)]

    def attempt(index: int) -> int:
        return book_lesson(client, academy, index % 2, "10:00", people[index]).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = sorted(pool.map(attempt, range(4)))
    assert results == [201, 201, 409, 409]
    assert [status for _, status in rooms_held(engine)].count("scheduled") == 2
    assert {room for room, _ in rooms_held(engine)} == {"Court 1", "Court 2"}


def test_clients_book_a_lesson_in_the_app(
    client: TestClient, academy: dict, auth: AuthHeaders
) -> None:
    client.patch(
        "/tenants/current",
        json={"requires_health_declaration": False, "booking_requires_plan": False},
        headers=academy["headers"],
    )
    user = uuid4()
    join(client, auth, user, join_code(client, academy))
    me = auth(user, academy["tenant_id"])
    services = client.get("/client/appointments/services", headers=me).json()
    assert [s["needs_resource"] for s in services if s["id"] == academy["lesson"]["id"]] == [True]
    params = {"service_id": academy["lesson"]["id"], "date": academy["day"].isoformat()}
    slots = client.get("/client/appointments/slots", params=params, headers=me).json()
    booked = client.post(
        "/client/appointments",
        json={
            "service_id": academy["lesson"]["id"],
            "staff_user_id": slots[0]["staff_user_id"],
            "starts_at": slots[0]["starts_at"],
            "room_id": slots[0]["room_id"],
        },
        headers=me,
    )
    assert booked.status_code == 201, booked.text
    assert booked.json()["my_booking"]["status"] == "booked"
    wrongly = client.post(
        "/client/appointments",
        json={
            "service_id": academy["lesson"]["id"],
            "staff_user_id": slots[0]["staff_user_id"],
            "starts_at": at(academy["day"] + timedelta(days=1), "10:00"),
            "room_id": str(uuid4()),
        },
        headers=me,
    )
    assert wrongly.status_code == 404


def test_a_room_is_refused_for_a_service_without_one(client: TestClient, academy: dict) -> None:
    headers = academy["headers"]
    plain = client.post(
        "/services",
        json={"name": "Plain", "duration_minutes": 30, "booking_mode": "appointment"},
        headers=headers,
    ).json()
    dana = new_client(client, headers, "Dana")
    body = {
        "service_id": plain["id"],
        "staff_user_id": str(academy["owner"]),
        "starts_at": at(academy["day"], "10:00"),
        "client_id": dana,
        "room_id": academy["courts"][0]["id"],
    }
    refused = client.post("/appointments", json=body, headers=headers)
    assert refused.status_code == 422 and refused.json()["detail"] == "no_room_used"
    del body["room_id"]
    assert client.post("/appointments", json=body, headers=headers).status_code == 201


def test_other_businesses_see_nothing(client: TestClient, academy: dict, auth: AuthHeaders) -> None:
    other = uuid4()
    business = {"name": "Other", "vertical": "fitness", "locale": "en",
                "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip
    tenant_id = client.post("/tenants", json=business, headers=auth(other)).json()["id"]
    theirs = auth(other, tenant_id)
    rooms = client.get(f"/services/{academy['lesson']['id']}/rooms", headers=theirs)
    assert rooms.status_code == 404
    params = {"service_id": academy["lesson"]["id"], "date": academy["day"].isoformat()}
    assert client.get("/appointments/slots", params=params, headers=theirs).status_code == 404


def test_a_standing_lesson_gets_a_court_each_week(
    client: TestClient, academy: dict, engine: Engine
) -> None:
    headers = academy["headers"]
    dana = new_client(client, headers, "Dana")
    made = client.post(
        "/series",
        json={
            "client_id": dana,
            "kind": "appointment",
            "service_id": academy["lesson"]["id"],
            "staff_user_id": str(academy["owner"]),
            "starts_at": at(academy["day"], "10:00"),
            "occurrences": 3,
        },
        headers=headers,
    )
    assert made.status_code == 201, made.text
    assert [r["outcome"] for r in made.json()["results"]] == ["booked"] * 3
    assert rooms_held(engine) == [("Court 1", "scheduled")] * 3
