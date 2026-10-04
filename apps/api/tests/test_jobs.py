from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.jobs import HORIZON_DAYS, extend_series
from tests.conftest import local_today
from tests.test_bookings import book, new_client


def create_series(client: TestClient, studio: dict, ends_on: str | None = None) -> dict:
    repeat = {"weekdays": [0, 3]}  # Mondays and Thursdays
    if ends_on:
        repeat["ends_on"] = ends_on
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": local_today().isoformat(),
            "start_time": "18:00",
            "repeat": repeat,
        },
        headers=studio["headers"],
    )
    assert created.status_code == 201, created.text
    return created.json()


def count(client: TestClient, studio: dict, start, days: int) -> int:
    total = 0
    for offset in range(0, days, 42):
        response = client.get(
            "/sessions",
            params={"start": (start + timedelta(days=offset)).isoformat(), "days": 42},
            headers=studio["headers"],
        )
        total += len(response.json())
    return total


def test_open_series_is_extended_and_reruns_add_nothing(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    series = create_series(client, studio)
    first = len(series["session_ids"])
    session = client.get(f"/sessions/{series['session_ids'][0]}", headers=studio["headers"]).json()
    assert session["series_open_ended"] is True

    in_four_weeks = datetime.now(UTC) + timedelta(days=28)
    with engine.begin() as connection:
        added = extend_series(connection, in_four_weeks)
    with engine.begin() as connection:
        again = extend_series(connection, in_four_weeks)

    assert added == 8  # four more weeks, two sessions a week
    assert again == 0
    total = count(client, studio, local_today(), HORIZON_DAYS + 42)
    assert total == first + 8


def test_series_with_an_end_date_is_left_alone(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    end = (local_today() + timedelta(days=13)).isoformat()
    series = create_series(client, studio, ends_on=end)

    with engine.begin() as connection:
        added = extend_series(connection, datetime.now(UTC) + timedelta(days=60))

    assert added == 0
    session = client.get(f"/sessions/{series['session_ids'][0]}", headers=studio["headers"]).json()
    assert session["series_open_ended"] is False


def test_ending_a_series_cancels_later_unbooked_sessions(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    series = create_series(client, studio)
    ids = series["session_ids"]
    booked_later = ids[6]
    book(client, studio["headers"], booked_later, new_client(client, studio["headers"], "Dana"))
    last_date = (local_today() + timedelta(days=14)).isoformat()

    ended = client.post(
        f"/series/{series['series_id']}/end",
        json={"last_date": last_date},
        headers=studio["headers"],
    )

    assert ended.status_code == 200, ended.text
    result = ended.json()
    assert result["kept"] == 1
    statuses = [
        client.get(f"/sessions/{session_id}", headers=studio["headers"]).json()["status"]
        for session_id in ids
    ]
    assert result["cancelled"] == statuses.count("cancelled") > 0
    kept = client.get(f"/sessions/{booked_later}", headers=studio["headers"]).json()
    assert kept["status"] == "scheduled"
    with engine.begin() as connection:
        assert extend_series(connection, datetime.now(UTC) + timedelta(days=90)) == 0


def test_ending_needs_schedule_write(client: TestClient, studio: dict, auth) -> None:
    series = create_series(client, studio)
    coach = auth(studio["coach"], studio["tenant_id"])
    response = client.post(
        f"/series/{series['series_id']}/end",
        json={"last_date": local_today().isoformat()},
        headers=coach,
    )
    assert response.status_code == 403


def test_changing_a_series_from_a_date_moves_later_sessions(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    series = create_series(client, studio)
    ids = series["session_ids"]
    booked = ids[3]
    client_id = new_client(client, studio["headers"], "Dana")
    book(client, studio["headers"], booked, client_id)
    third = client.get(f"/sessions/{ids[2]}", headers=studio["headers"]).json()
    from_date = third["starts_at"][:10]  # 18:00 Israel time is still the same UTC date

    changed = client.patch(
        f"/series/{series['series_id']}",
        json={
            "from_date": from_date,
            "start_time": "19:30",
            "duration_minutes": 45,
            "capacity": 6,
            "notes": "New time",
        },
        headers=studio["headers"],
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["updated"] == len(ids) - 2
    first = client.get(f"/sessions/{ids[0]}", headers=studio["headers"]).json()
    later = client.get(f"/sessions/{booked}", headers=studio["headers"]).json()
    assert "T15:00" in first["starts_at"] or "T16:00" in first["starts_at"]  # unchanged 18:00
    assert later["capacity"] == 6 and later["notes"] == "New time"
    start = datetime.fromisoformat(later["starts_at"])
    end = datetime.fromisoformat(later["ends_at"])
    assert (end - start) == timedelta(minutes=45)
    assert start.astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%H:%M") == "19:30"
    roster = client.get(f"/sessions/{booked}/bookings", headers=studio["headers"]).json()
    assert roster[0]["status"] == "booked"  # bookings follow the session
    # New occurrences from the daily job use the new time too.
    with engine.begin() as connection:
        extend_series(connection, datetime.now(UTC) + timedelta(days=28))
    sessions = client.get(
        "/sessions",
        params={"start": (local_today() + timedelta(days=84)).isoformat(), "days": 28},
        headers=studio["headers"],
    ).json()
    assert sessions
    assert all(
        datetime.fromisoformat(s["starts_at"]).astimezone(ZoneInfo("Asia/Jerusalem")).hour == 19
        for s in sessions
    )


def test_copy_week_copies_one_off_sessions_once(client: TestClient, studio: dict) -> None:
    monday = local_today() + timedelta(days=7 - local_today().weekday())
    for offset, hour in ((0, "07:00"), (2, "18:00")):
        client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": (monday + timedelta(days=offset)).isoformat(),
                "start_time": hour,
            },
            headers=studio["headers"],
        )
    create_series(client, studio)  # series are not copied
    body = {"from_date": monday.isoformat(), "to_date": (monday + timedelta(days=7)).isoformat()}

    first = client.post("/sessions/copy-week", json=body, headers=studio["headers"]).json()
    again = client.post("/sessions/copy-week", json=body, headers=studio["headers"]).json()
    odd = client.post(
        "/sessions/copy-week",
        json={"from_date": monday.isoformat(), "to_date": (monday + timedelta(days=3)).isoformat()},
        headers=studio["headers"],
    )

    assert first == {"created": 2, "skipped": 0}
    assert again == {"created": 0, "skipped": 2}
    assert odd.status_code == 422
    week = client.get(
        "/sessions",
        params={"start": (monday + timedelta(days=7)).isoformat(), "days": 7},
        headers=studio["headers"],
    ).json()
    one_offs = [s for s in week if s["series_id"] is None]
    times = sorted(
        datetime.fromisoformat(s["starts_at"])
        .astimezone(ZoneInfo("Asia/Jerusalem"))
        .strftime("%a %H:%M")
        for s in one_offs
    )
    assert times == ["Mon 07:00", "Wed 18:00"]


def test_series_change_and_copy_need_schedule_write(client: TestClient, studio: dict, auth) -> None:
    series = create_series(client, studio)
    coach = auth(studio["coach"], studio["tenant_id"])
    change = client.patch(
        f"/series/{series['series_id']}",
        json={
            "from_date": local_today().isoformat(),
            "start_time": "19:00",
            "duration_minutes": 60,
            "capacity": 5,
        },
        headers=coach,
    )
    copy = client.post(
        "/sessions/copy-week",
        json={
            "from_date": local_today().isoformat(),
            "to_date": (local_today() + timedelta(days=7)).isoformat(),
        },
        headers=coach,
    )
    assert change.status_code == 403 and copy.status_code == 403
