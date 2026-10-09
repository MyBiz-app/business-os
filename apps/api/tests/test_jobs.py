from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

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
    with engine.connect() as connection:
        moved = (
            connection.execute(
                text("SELECT payload FROM app.notifications WHERE kind = 'session_moved'")
            )
            .scalars()
            .all()
        )
    assert len(moved) == 1  # only Dana, only her session
    assert moved[0]["session_id"] == booked and moved[0]["service_name"]
    assert datetime.fromisoformat(moved[0]["starts_at"]) == start
    assert datetime.fromisoformat(moved[0]["previous_starts_at"]) != start
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


def test_todays_booked_clients_are_reminded_once(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from app.jobs import remind_sessions
    from app.schedule.scheduling import local_to_utc

    today = local_today()
    later_today = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": today.isoformat(),
            "start_time": "23:30",
        },
        headers=studio["headers"],
    ).json()["session_ids"][0]
    tomorrow = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": (today + timedelta(days=1)).isoformat(),
            "start_time": "07:00",
        },
        headers=studio["headers"],
    ).json()["session_ids"][0]
    dana = new_client(client, studio["headers"], "Dana")
    book(client, studio["headers"], later_today, dana)
    book(client, studio["headers"], tomorrow, dana)
    morning = local_to_utc(today, datetime.min.time().replace(hour=5), "Asia/Jerusalem")

    with engine.begin() as connection:
        first = remind_sessions(connection, morning)
    with engine.begin() as connection:
        again = remind_sessions(connection, morning)
        kinds = (
            connection.execute(
                text(
                    "SELECT payload->>'session_id' FROM app.notifications "
                    "WHERE kind = 'session_reminder'"
                )
            )
            .scalars()
            .all()
        )

    assert first == 1 and again == 0
    assert kinds == [later_today]


def test_clients_hear_once_when_their_last_plan_ends_soon(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from app.jobs import remind_plans
    from tests.test_client_app import give_plan

    ending = new_client(client, studio["headers"], "Dana")
    renewed = new_client(client, studio["headers"], "Noa")
    give_plan(client, studio, ending)
    give_plan(client, studio, renewed)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.entitlements SET ends_on = :d"),
            {"d": local_today() + timedelta(days=2)},
        )
    later = client.get("/plans", headers=studio["headers"]).json()[0]
    client.post(
        f"/clients/{renewed}/entitlements",
        json={
            "plan_id": later["id"],
            "starts_on": (local_today() + timedelta(days=3)).isoformat(),
            "idempotency_key": "renewal-0001",
        },
        headers=studio["headers"],
    )

    with engine.begin() as connection:
        first = remind_plans(connection)
    with engine.begin() as connection:
        again = remind_plans(connection)
        notified = connection.execute(
            text(
                "SELECT client_id::text, payload FROM app.notifications WHERE kind = 'plan_ending'"
            )
        ).all()

    assert first == 1 and again == 0
    [(client_id, payload)] = notified
    assert client_id == ending
    assert payload["ends_on"] == (local_today() + timedelta(days=2)).isoformat()


def test_closed_day_cancels_its_sessions_and_series_skip_it(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    series = create_series(client, studio)
    first = client.get(f"/sessions/{series['session_ids'][1]}", headers=studio["headers"]).json()
    closed = datetime.fromisoformat(first["starts_at"]).astimezone(ZoneInfo("Asia/Jerusalem"))
    booked = new_client(client, studio["headers"], "Dana")
    book(client, studio["headers"], first["id"], booked)

    response = client.post(
        "/closed-days",
        json={"day": closed.date().isoformat(), "reason": "Holiday"},
        headers=studio["headers"],
    )
    again = client.post(
        "/closed-days", json={"day": closed.date().isoformat()}, headers=studio["headers"]
    )

    assert response.status_code == 201, response.text
    assert response.json()["cancelled_sessions"] == 1
    assert again.status_code == 409
    session = client.get(f"/sessions/{first['id']}", headers=studio["headers"]).json()
    assert session["status"] == "cancelled"
    with engine.connect() as connection:
        notes = connection.execute(text("SELECT kind, payload FROM app.notifications")).all()
    cancelled = [payload for kind, payload in notes if kind == "session_cancelled"]
    assert len(cancelled) == 1  # Dana was booked
    assert cancelled[0]["session_id"] == first["id"]
    assert cancelled[0]["service_name"] and cancelled[0]["starts_at"]
    listed = client.get("/closed-days", headers=studio["headers"]).json()
    assert [d["reason"] for d in listed] == ["Holiday"]

    # Reopening the day: it leaves the list, the cancelled session stays cancelled.
    reopened = client.delete(f"/closed-days/{listed[0]['id']}", headers=studio["headers"])
    assert reopened.status_code == 204
    assert client.get("/closed-days", headers=studio["headers"]).json() == []
    gone = client.delete(f"/closed-days/{listed[0]['id']}", headers=studio["headers"])
    assert gone.status_code == 404
    still = client.get(f"/sessions/{first['id']}", headers=studio["headers"]).json()
    assert still["status"] == "cancelled"

    # A closed day far ahead: the daily job doesn't create a session on it.
    far = local_today() + timedelta(days=HORIZON_DAYS + 14)
    while far.weekday() not in (0, 3):
        far += timedelta(days=1)
    client.post("/closed-days", json={"day": far.isoformat()}, headers=studio["headers"])
    with engine.begin() as connection:
        extend_series(connection, datetime.now(UTC) + timedelta(days=28))
    on_far = client.get(
        "/sessions", params={"start": far.isoformat(), "days": 1}, headers=studio["headers"]
    ).json()
    assert on_far == []


def test_closing_days_needs_schedule_write(client: TestClient, studio: dict, auth) -> None:
    coach = auth(studio["coach"], studio["tenant_id"])
    response = client.post("/closed-days", json={"day": local_today().isoformat()}, headers=coach)
    assert response.status_code == 403


def test_reminders_also_go_out_on_whatsapp_with_the_module(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from app.jobs import message_reminders, remind_sessions
    from app.schedule.scheduling import local_to_utc

    headers = studio["headers"]
    today = local_today()
    session = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": today.isoformat(),
            "start_time": "23:30",
        },
        headers=headers,
    ).json()["session_ids"][0]
    dana = client.post(
        "/clients", json={"first_name": "Dana", "phone": "050-1111111"}, headers=headers
    ).json()["id"]
    silent = new_client(client, headers, "NoPhone")
    book(client, headers, session, dana)
    book(client, headers, session, silent)
    morning = local_to_utc(today, datetime.min.time().replace(hour=5), "Asia/Jerusalem")

    with engine.begin() as connection:
        remind_sessions(connection, morning)
        assert message_reminders(connection) == 0  # no messaging module yet
    client.put("/tenants/current/modules", json={"modules": {"whatsapp": 1}}, headers=headers)
    with engine.begin() as connection:
        sent = message_reminders(connection)
        again = message_reminders(connection)

    assert sent == 1 and again == 0
    [message] = client.get("/messages", params={"client_id": dana}, headers=headers).json()
    assert message["channel"] == "whatsapp" and "Pilates" in message["body"]
    assert "Dana" in message["body"]


def test_untouched_leads_get_one_follow_up_on_autopilot(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from app.jobs import follow_up_leads

    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"crm": 1}}, headers=headers)
    lead = client.post(
        "/leads",
        json={"first_name": "Lior", "phone": "052-3333333", "interest": "Pilates"},
        headers=headers,
    ).json()
    quiet = client.post("/leads", json={"first_name": "NoPhone"}, headers=headers).json()
    later = datetime.now(UTC) + timedelta(days=3)

    with engine.begin() as connection:
        assert follow_up_leads(connection, later) == 0  # no autopilot or WhatsApp yet
    modules = {"crm": 1, "crm_automation": 1, "whatsapp": 1}
    client.put("/tenants/current/modules", json={"modules": modules}, headers=headers)
    with engine.begin() as connection:
        assert follow_up_leads(connection, datetime.now(UTC)) == 0  # too soon
        sent = follow_up_leads(connection, later)
        again = follow_up_leads(connection, later + timedelta(days=3))

    assert sent == 1 and again == 0
    [message] = client.get("/messages", params={"lead_id": lead["id"]}, headers=headers).json()
    assert message["channel"] == "whatsapp" and "Lior" in message["body"]
    assert "Pilates" in message["body"] and "Studio Flow" in message["body"]
    timeline = client.get(f"/leads/{lead['id']}", headers=headers).json()
    assert any(a["kind"] == "message" for a in timeline["activities"])
    assert client.get("/messages", params={"lead_id": quiet["id"]}, headers=headers).json() == []
