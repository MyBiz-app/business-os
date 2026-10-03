from datetime import UTC, datetime, timedelta

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
