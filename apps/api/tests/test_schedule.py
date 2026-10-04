from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_tenants import STUDIO


def week(client: TestClient, headers: dict, start: str = "2026-10-11", days: int = 7) -> list:
    response = client.get("/sessions", params={"start": start, "days": days}, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_single_session_uses_service_defaults_and_local_time(
    client: TestClient, studio: dict
) -> None:
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": "2026-10-12",
            "start_time": "18:00",
            "location_id": studio["location"]["id"],
            "room_id": studio["room"]["id"],
            "instructor_user_id": str(studio["coach"]),
        },
        headers=studio["headers"],
    )

    assert created.status_code == 201
    assert created.json()["series_id"] is None
    [session] = week(client, studio["headers"])
    assert session["starts_at"].startswith("2026-10-12T15:00:00")  # 18:00 Israel = 15:00 UTC
    assert session["ends_at"].startswith("2026-10-12T15:55:00")
    assert session["capacity"] == 12
    assert session["service"]["name"] == "Pilates"
    assert session["room_name"] == "Studio A"
    assert session["instructor_email"] == f"{studio['coach']}@example.com"
    assert session["booked"] == 0


def test_weekly_series(client: TestClient, studio: dict) -> None:
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": "2026-10-11",
            "start_time": "07:00",
            "capacity": 8,
            "repeat": {"weekdays": [6, 1], "ends_on": "2026-10-31"},  # Sundays and Tuesdays
        },
        headers=studio["headers"],
    ).json()

    assert created["series_id"] is not None
    assert len(created["session_ids"]) == 6
    first_week = week(client, studio["headers"])
    assert [s["starts_at"][:10] for s in first_week] == ["2026-10-11", "2026-10-13"]
    assert {s["capacity"] for s in first_week} == {8}
    assert len(week(client, studio["headers"], days=42)) == 6


def test_series_is_bounded(client: TestClient, studio: dict) -> None:
    base = {"service_id": studio["service"]["id"], "date": "2026-10-11", "start_time": "07:00"}
    too_long = {**base, "repeat": {"weekdays": [6], "ends_on": "2027-10-11"}}
    backwards = {**base, "repeat": {"weekdays": [6], "ends_on": "2026-10-01"}}
    bad_day = {**base, "repeat": {"weekdays": [7]}}

    for body in (too_long, backwards, bad_day):
        assert client.post("/sessions", json=body, headers=studio["headers"]).status_code == 422


def test_default_series_length_is_twelve_weeks(client: TestClient, studio: dict) -> None:
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": "2026-10-11",
            "start_time": "07:00",
            "repeat": {"weekdays": [6]},
        },
        headers=studio["headers"],
    ).json()

    assert len(created["session_ids"]) == 13  # 12 weeks after the first Sunday, inclusive


def test_edit_one_occurrence(client: TestClient, studio: dict) -> None:
    ids = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": "2026-10-11",
            "start_time": "07:00",
            "repeat": {"weekdays": [6], "ends_on": "2026-10-25"},
        },
        headers=studio["headers"],
    ).json()["session_ids"]

    moved = client.patch(
        f"/sessions/{ids[0]}",
        json={"start_time": "08:30", "capacity": 4, "notes": "Sub teacher"},
        headers=studio["headers"],
    ).json()
    cancelled = client.patch(
        f"/sessions/{ids[1]}", json={"status": "cancelled"}, headers=studio["headers"]
    ).json()
    untouched = client.get(f"/sessions/{ids[2]}", headers=studio["headers"]).json()

    assert moved["starts_at"].startswith("2026-10-11T05:30:00")
    assert moved["ends_at"].startswith("2026-10-11T06:25:00")  # duration kept
    assert moved["capacity"] == 4
    assert moved["notes"] == "Sub teacher"
    assert cancelled["status"] == "cancelled"
    assert untouched["starts_at"].startswith("2026-10-25T05:00:00")
    assert untouched["status"] == "scheduled"


def test_references_must_belong_to_the_business(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    theirs = auth(other_owner, other_tenant)
    their_service = client.post(
        "/services", json={"name": "X", "duration_minutes": 30}, headers=theirs
    ).json()
    other_location = client.post(
        "/locations", json={"name": "Second"}, headers=studio["headers"]
    ).json()
    base = {"service_id": studio["service"]["id"], "date": "2026-10-12", "start_time": "18:00"}

    cases = [
        {**base, "service_id": their_service["id"]},
        {**base, "location_id": other_location["id"], "room_id": studio["room"]["id"]},
        {**base, "room_id": studio["room"]["id"]},
        {**base, "instructor_user_id": str(uuid4())},
    ]
    for body in cases:
        response = client.post("/sessions", json=body, headers=studio["headers"])
        assert response.status_code == 422, body


def test_schedule_permissions(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    body = {"service_id": studio["service"]["id"], "date": "2026-10-12", "start_time": "18:00"}
    coach_headers = auth(studio["coach"], studio["tenant_id"])

    assert (
        client.get("/sessions", params={"start": "2026-10-11"}, headers=coach_headers).status_code
        == 200
    )
    assert client.post("/sessions", json=body, headers=coach_headers).status_code == 403
    desk_headers = auth(desk, studio["tenant_id"])
    assert client.post("/sessions", json=body, headers=desk_headers).status_code == 201


def test_schedule_is_isolated_between_businesses(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    [session_id] = client.post(
        "/sessions",
        json={"service_id": studio["service"]["id"], "date": "2026-10-12", "start_time": "18:00"},
        headers=studio["headers"],
    ).json()["session_ids"]
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    theirs = auth(other_owner, other_tenant)

    assert week(client, theirs) == []
    assert client.get(f"/sessions/{session_id}", headers=theirs).status_code == 404
    patch = client.patch(f"/sessions/{session_id}", json={"capacity": 1}, headers=theirs)
    assert patch.status_code == 404


def test_options_for_the_session_form(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")

    options = client.get("/sessions/options", headers=auth(desk, studio["tenant_id"])).json()
    staff_view = client.get("/sessions/options", headers=auth(studio["coach"], studio["tenant_id"]))

    assert [s["name"] for s in options["services"]] == ["Pilates"]
    assert options["rooms"] == [
        {
            "id": studio["room"]["id"],
            "name": "Studio A",
            "location_id": studio["location"]["id"],
        }
    ]
    assert len(options["instructors"]) == 3  # owner, coach, front desk
    assert staff_view.status_code == 403


def test_instructors_list_only_their_sessions(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    day = (local_today() + timedelta(days=3)).isoformat()
    for instructor in (str(studio["coach"]), None):
        client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": day,
                "start_time": "18:00" if instructor else "19:00",
                "instructor_user_id": instructor,
            },
            headers=studio["headers"],
        )
    coach = auth(studio["coach"], studio["tenant_id"])

    mine = client.get("/sessions", params={"start": day, "days": 1, "mine": True}, headers=coach)
    everything = client.get("/sessions", params={"start": day, "days": 1}, headers=coach)

    assert [s["instructor_user_id"] for s in mine.json()] == [str(studio["coach"])]
    assert len(everything.json()) == 2
