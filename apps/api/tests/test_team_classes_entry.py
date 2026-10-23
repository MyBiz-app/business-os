"""Several instructors for one class (a ratio) and open entry (check in, no class)."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_bookings import new_client
from tests.test_plans import card, sell
from tests.test_tenants import STUDIO


def class_session(client: TestClient, studio: dict, service_id: str, **extra) -> dict:
    body = {
        "service_id": service_id,
        "date": (local_today() + timedelta(days=10)).isoformat(),
        "start_time": "17:00",
        **extra,
    }
    return client.post("/sessions", json=body, headers=studio["headers"])


def academy(client: TestClient, studio: dict, ratio: int | None = 8) -> str:
    created = client.post(
        "/services",
        json={
            "name": "Kids academy",
            "duration_minutes": 60,
            "capacity": 24,
            "participants_per_instructor": ratio,
        },
        headers=studio["headers"],
    )
    assert created.status_code == 201, created.text
    assert created.json()["participants_per_instructor"] == ratio
    return created.json()["id"]


def test_class_runs_with_several_instructors(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    service_id = academy(client, studio)
    second, third = uuid4(), uuid4()
    for user in (second, third):
        add_member(engine, studio["tenant_id"], user, "staff")

    created = class_session(
        client,
        studio,
        service_id,
        instructor_user_id=str(studio["coach"]),
        extra_instructor_user_ids=[str(second), str(third)],
    )

    assert created.status_code == 201, created.text
    [session_id] = created.json()["session_ids"]
    session = client.get(f"/sessions/{session_id}", headers=studio["headers"]).json()
    assert session["capacity"] == 24
    assert [i["lead"] for i in session["instructors"]] == [True, False, False]
    assert session["instructors"][0]["user_id"] == str(studio["coach"])
    assert {i["user_id"] for i in session["instructors"][1:]} == {str(second), str(third)}
    assert session["participants_per_instructor"] == 8


def test_ratio_limits_capacity(client: TestClient, studio: dict, engine: Engine) -> None:
    service_id = academy(client, studio)
    second = uuid4()
    add_member(engine, studio["tenant_id"], second, "staff")

    too_many = class_session(
        client,
        studio,
        service_id,
        instructor_user_id=str(studio["coach"]),
        extra_instructor_user_ids=[str(second)],
    )  # 24 people, 2 instructors x 8 = 16
    assert too_many.status_code == 422
    assert too_many.json()["detail"] == "ratio_exceeded"

    fine = class_session(
        client,
        studio,
        service_id,
        instructor_user_id=str(studio["coach"]),
        extra_instructor_user_ids=[str(second)],
        capacity=16,
    )
    assert fine.status_code == 201
    [session_id] = fine.json()["session_ids"]
    raised = client.patch(
        f"/sessions/{session_id}", json={"capacity": 17}, headers=studio["headers"]
    )
    assert raised.status_code == 422
    assert raised.json()["detail"] == "ratio_exceeded"
    # A third instructor makes room for more.
    third = uuid4()
    add_member(engine, studio["tenant_id"], third, "staff")
    team = client.patch(
        f"/sessions/{session_id}",
        json={"extra_instructor_user_ids": [str(second), str(third)], "capacity": 24},
        headers=studio["headers"],
    )
    assert team.status_code == 200, team.text
    assert len(team.json()["instructors"]) == 3
    # Taking one away without lowering the capacity is refused.
    fewer = client.patch(
        f"/sessions/{session_id}",
        json={"extra_instructor_user_ids": []},
        headers=studio["headers"],
    )
    assert fewer.status_code == 422


def test_team_must_be_members_and_distinct(client: TestClient, studio: dict) -> None:
    service_id = academy(client, studio, ratio=None)

    stranger = class_session(client, studio, service_id, extra_instructor_user_ids=[str(uuid4())])
    assert stranger.status_code == 422

    lead_twice = class_session(
        client,
        studio,
        service_id,
        instructor_user_id=str(studio["coach"]),
        extra_instructor_user_ids=[str(studio["coach"])],
    )
    assert lead_twice.status_code == 422


def test_team_follows_a_weekly_series_and_the_my_sessions_filter(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    service_id = academy(client, studio, ratio=None)
    second = uuid4()
    add_member(engine, studio["tenant_id"], second, "staff")
    start = local_today() + timedelta(days=1)

    created = class_session(
        client,
        studio,
        service_id,
        date=start.isoformat(),
        instructor_user_id=str(studio["coach"]),
        extra_instructor_user_ids=[str(second)],
        repeat={"weekdays": list(range(7)), "ends_on": (start + timedelta(days=2)).isoformat()},
    )

    assert created.status_code == 201, created.text
    sessions = client.get(
        "/sessions", params={"start": start.isoformat(), "days": 3}, headers=studio["headers"]
    ).json()
    assert len(sessions) == 3
    assert all(len(s["instructors"]) == 2 for s in sessions)
    with engine.begin() as connection:
        stored = connection.execute(
            text("SELECT extra_instructor_user_ids FROM app.session_series")
        ).scalar_one()
    assert stored == [second]


def test_open_entry_service_needs_class_mode(client: TestClient, studio: dict) -> None:
    gym = client.post(
        "/services",
        json={"name": "Open gym", "duration_minutes": 60, "capacity": 100, "open_entry": True},
        headers=studio["headers"],
    )
    assert gym.status_code == 201
    assert gym.json()["open_entry"] is True

    wrong = client.post(
        "/services",
        json={
            "name": "Haircut",
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "open_entry": True,
        },
        headers=studio["headers"],
    )
    assert wrong.status_code == 422

    haircut = client.post(
        "/services",
        json={"name": "Cut", "duration_minutes": 30, "booking_mode": "appointment"},
        headers=studio["headers"],
    ).json()
    flipped = client.patch(
        f"/services/{haircut['id']}", json={"open_entry": True}, headers=studio["headers"]
    )
    assert flipped.status_code == 422
    assert flipped.json()["detail"] == "invalid_open_entry"


def open_hours(engine: Engine, studio: dict, service_id: str, *, now: bool = True) -> str:
    """Opening hours around now (or well after it), as an entry service has them."""
    offset = "-1 hour" if now else "+5 hours"
    with engine.begin() as connection:
        return str(
            connection.execute(
                text(f"""
                    INSERT INTO app.sessions
                        (tenant_id, service_id, location_id, capacity, starts_at, ends_at)
                    VALUES (:t, :s, :l, 1000, now() + interval '{offset}',
                            now() + interval '{offset}' + interval '2 hours')
                    RETURNING id
                """),
                {"t": studio["tenant_id"], "s": service_id, "l": studio["location"]["id"]},
            ).scalar_one()
        )


def open_gym(client: TestClient, studio: dict) -> str:
    created = client.post(
        "/services",
        json={"name": "Open gym", "duration_minutes": 60, "capacity": 100, "open_entry": True},
        headers=studio["headers"],
    )
    return created.json()["id"]


def test_client_checks_in_with_a_plan(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    gym = open_gym(client, studio)
    session_id = open_hours(engine, studio, gym)
    dana = new_client(client, headers, "Dana")
    sell(client, headers, dana, card(client, headers, credits=2)["id"])

    entry = client.post("/entries", json={"client_id": dana, "service_id": gym}, headers=headers)

    assert entry.status_code == 201, entry.text
    assert entry.json()["status"] == "checked_in"
    assert entry.json()["session_id"] == session_id
    assert entry.json()["plan_name"] == "2-class card"
    assert entry.json()["checked_in_at"] is not None
    again = client.post("/entries", json={"client_id": dana, "service_id": gym}, headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "already_booked"


def test_entry_without_plan_needs_the_desk_to_allow_it(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    gym = open_gym(client, studio)
    open_hours(engine, studio, gym)
    noa = new_client(client, headers, "Noa")

    refused = client.post("/entries", json={"client_id": noa, "service_id": gym}, headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "no_valid_plan"

    allowed = client.post(
        "/entries",
        json={"client_id": noa, "service_id": gym, "without_plan": True},
        headers=headers,
    )
    assert allowed.status_code == 201
    assert allowed.json()["status"] == "checked_in"
    assert allowed.json()["plan_name"] is None


def test_entry_is_closed_outside_opening_hours_and_for_classes(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    gym = open_gym(client, studio)
    open_hours(engine, studio, gym, now=False)  # opens in five hours
    yael = new_client(client, headers, "Yael")
    body = {"client_id": yael, "service_id": gym, "without_plan": True}

    closed = client.post("/entries", json=body, headers=headers)
    assert closed.status_code == 409
    assert closed.json()["detail"] == "entry_closed"

    # An ordinary class is not entry, even when it is on right now.
    class_id = studio["service"]["id"]
    open_hours(engine, studio, class_id)
    not_entry = client.post("/entries", json={**body, "service_id": class_id}, headers=headers)
    assert not_entry.status_code == 409
    assert not_entry.json()["detail"] == "entry_closed"


def test_other_businesses_cannot_use_my_entry_or_my_team(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    gym = open_gym(client, studio)
    open_hours(engine, studio, gym)
    outsider = uuid4()
    tenant_id = client.post("/tenants", json=STUDIO, headers=auth(outsider)).json()["id"]
    theirs = auth(outsider, tenant_id)
    visitor = new_client(client, theirs, "Visitor")

    entry = client.post(
        "/entries",
        json={"client_id": visitor, "service_id": gym, "without_plan": True},
        headers=theirs,
    )
    assert entry.status_code == 409
    assert entry.json()["detail"] == "entry_closed"

    own_service = client.post(
        "/services", json={"name": "Yoga", "duration_minutes": 60, "capacity": 10}, headers=theirs
    ).json()["id"]
    borrowed = client.post(
        "/sessions",
        json={
            "service_id": own_service,
            "date": (local_today() + timedelta(days=3)).isoformat(),
            "start_time": "10:00",
            "extra_instructor_user_ids": [str(studio["coach"])],
        },
        headers=theirs,
    )
    assert borrowed.status_code == 422
