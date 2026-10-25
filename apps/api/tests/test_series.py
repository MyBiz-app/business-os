# ruff: noqa: F811, F401
"""Booking series (slice C5): a standing court or appointment, and a course joined once."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.schedule.series import occurrence_starts
from tests.conftest import AuthHeaders, local_today
from tests.test_appointments import at, barber, local_times
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code
from tests.test_resources import club, club_member, reservation


def week(day, n: int):
    return day + timedelta(weeks=n)


def court_series(club: dict, client_id: str, **extra) -> dict:
    return {
        "kind": "resource",
        "service_id": club["padel"]["id"],
        "room_id": club["courts"][0]["id"],
        "starts_at": at(club["day"], "19:00"),
        "minutes": 60,
        "occurrences": 4,
        "client_id": client_id,
        **extra,
    }


def test_dates_keep_the_business_clock_across_a_clock_change() -> None:
    first = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)  # 19:00 in Israel (UTC+3)
    dates = list(occurrence_starts(first, 1, 3, "Asia/Jerusalem"))
    # The clock goes back on 25 October: 19:00 is then 17:00 UTC.
    assert [d.hour for d in dates] == [16, 17, 17]
    assert [d.day for d in dates] == [20, 27, 3]
    fortnightly = list(occurrence_starts(first, 2, 2, "Asia/Jerusalem"))
    assert fortnightly[1].day == 3


def test_a_standing_court_skips_taken_dates_and_cancels_in_one_go(
    client: TestClient, club: dict
) -> None:
    headers, day = club["headers"], club["day"]
    dana = new_client(client, headers, "Dana")
    omer = new_client(client, headers, "Omer")
    # Someone else already holds Court 1 at 19:00 in the third week.
    blocker = reservation(club, 0, "19:00", 60, omer)
    blocker["starts_at"] = at(week(day, 2), "19:00")
    assert client.post("/resources/reservations", json=blocker, headers=headers).status_code == 201

    made = client.post("/series", json=court_series(club, dana), headers=headers)

    assert made.status_code == 201, made.text
    series = made.json()
    assert [r["outcome"] for r in series["results"]] == ["booked", "booked", "skipped", "booked"]
    assert series["results"][2]["reason"] == "slot_taken"
    assert series["upcoming"] == 3 and series["status"] == "active"
    shown = client.get(f"/clients/{dana}/series", headers=headers).json()
    assert [s["id"] for s in shown] == [series["id"]]
    # The booked dates are ordinary reservations: Court 1 is no longer free then.
    params = {"service_id": club["padel"]["id"], "date": week(day, 1).isoformat(), "minutes": 60}

    def court_one_times() -> list[str]:
        slots = client.get("/resources/slots", params=params, headers=headers).json()
        return local_times([s for s in slots if s["room_name"] == "Court 1"])

    assert "19:00" not in court_one_times()

    cancelled = client.post(f"/series/{series['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["upcoming"] == 0
    assert "19:00" in court_one_times()  # released with the series


def test_a_series_with_no_free_date_is_refused(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    dana = new_client(client, headers, "Dana")
    omer = new_client(client, headers, "Omer")
    first = client.post("/series", json=court_series(club, omer), headers=headers)
    second = client.post("/series", json=court_series(club, dana), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409 and second.json()["detail"] == "no_date_available"
    assert client.get(f"/clients/{dana}/series", headers=headers).json() == []


def test_a_series_needs_what_its_kind_needs(client: TestClient, club: dict) -> None:
    headers = club["headers"]
    dana = new_client(client, headers, "Dana")
    no_room = court_series(club, dana) | {"room_id": None}
    once = court_series(club, dana) | {"occurrences": 1}
    too_long = court_series(club, dana) | {"occurrences": 53}
    for body in (no_room, once, too_long):
        assert client.post("/series", json=body, headers=headers).status_code == 422


def test_a_course_is_joined_once(client: TestClient, studio: dict) -> None:
    headers, service = studio["headers"], studio["service"]
    day = local_today() + timedelta(days=3)
    for n in (0, 1, 3):  # the course meets in weeks 1, 2 and 4; week 3 has no session
        made = client.post(
            "/sessions",
            json={"service_id": service["id"], "date": week(day, n).isoformat(),
                  "start_time": "18:00", "capacity": 2},
            headers=headers,
        )  # fmt: skip
        assert made.status_code == 201, made.text
    dana = new_client(client, headers, "Dana")

    made = client.post(
        "/series",
        json={"kind": "class", "service_id": service["id"], "starts_at": at(day, "18:00"),
              "occurrences": 4, "client_id": dana},
        headers=headers,
    )  # fmt: skip

    assert made.status_code == 201, made.text
    results = made.json()["results"]
    assert [r["outcome"] for r in results] == ["booked", "booked", "skipped", "booked"]
    assert results[2]["reason"] == "no_session"
    bookings = client.get(f"/clients/{dana}/bookings", headers=headers).json()
    assert len(bookings) == 3


def test_a_client_sets_up_a_standing_appointment_and_cancels_it(
    client: TestClient,
    barber: dict,
    auth: AuthHeaders,
) -> None:
    user = uuid4()
    join(client, auth, user, join_code(client, barber))
    me = auth(user, barber["tenant_id"])
    body = {
        "kind": "appointment",
        "service_id": barber["haircut"]["id"],
        "staff_user_id": str(barber["owner"]),
        "starts_at": at(barber["day"], "10:00"),
        "occurrences": 3,
        "every_weeks": 2,
    }

    made = client.post("/client/series", json=body, headers=me)

    assert made.status_code == 201, made.text
    assert [r["outcome"] for r in made.json()["results"]] == ["booked"] * 3
    mine = client.get("/client/series", headers=me).json()
    assert [s["id"] for s in mine] == [made.json()["id"]] and mine[0]["upcoming"] == 3
    # The business sees it too, with the client's name on each appointment.
    sessions = client.get(
        "/sessions",
        params={"start": barber["day"].isoformat(), "days": 1},
        headers=barber["headers"],
    ).json()
    assert [s["appointment_client"] for s in sessions] != []

    cancelled = client.post(f"/client/series/{made.json()['id']}/cancel", headers=me)
    assert cancelled.status_code == 200 and cancelled.json()["upcoming"] == 0
    assert client.get("/sessions", params={"start": barber["day"].isoformat(), "days": 1},
                      headers=barber["headers"]).json() == []  # fmt: skip


def test_a_court_paid_in_the_app_is_a_series_for_the_business(
    client: TestClient, club: dict, auth: AuthHeaders
) -> None:
    me = club_member(client, club, auth)
    body = court_series(club, "ignored")
    body.pop("client_id")

    refused = client.post("/client/series", json=body, headers=me)

    assert refused.status_code == 409 and refused.json()["detail"] == "series_needs_staff"
