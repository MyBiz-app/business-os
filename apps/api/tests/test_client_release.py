"""Class release for clients, the instructor on a class, and the profile status."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.schedule.release import compute_release
from tests.conftest import AuthHeaders, local_today
from tests.test_bookings import new_session
from tests.test_client_app import member
from tests.test_workspace import PNG

JERUSALEM = "Asia/Jerusalem"


def at(day: str, hour: int, minute: int = 0) -> datetime:
    local = datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00")
    return local.replace(tzinfo=UTC) - timedelta(hours=3)  # Jerusalem in late October (UTC+3)


def test_rolling_horizon_counts_today() -> None:
    release = compute_release(at("2026-10-14", 9), JERUSALEM, 7, None, None, None)

    assert release.published_until == date(2026, 10, 20)
    assert release.next_release_at is None


def test_weekly_release_opens_the_next_week_on_the_release_moment() -> None:
    thursday = 3  # 0 = Monday
    # Wed 2026-10-14, before Thursday 20:00: the rest of this Sunday-Saturday week is open.
    before = compute_release(at("2026-10-14", 9), JERUSALEM, 7, thursday, time(20), None)
    assert before.published_until == date(2026, 10, 17)
    assert before.next_release_at == at("2026-10-15", 20)

    # Thu 20:00 sharp: the whole next week opens, and the following release is a week away.
    after = compute_release(at("2026-10-15", 20), JERUSALEM, 7, thursday, time(20), None)
    assert after.published_until == date(2026, 10, 24)
    assert after.next_release_at == at("2026-10-22", 20)

    # Sunday starts the new week: its own Saturday is open until Thursday's release.
    sunday = compute_release(at("2026-10-18", 8), JERUSALEM, 7, thursday, time(20), None)
    assert sunday.published_until == date(2026, 10, 24)
    assert sunday.next_release_at == at("2026-10-22", 20)


def test_publishing_early_only_opens_more() -> None:
    release = compute_release(
        at("2026-10-14", 9), JERUSALEM, 7, 3, time(20), published_until=date(2026, 10, 24)
    )
    assert release.published_until == date(2026, 10, 24)
    behind = compute_release(
        at("2026-10-14", 9), JERUSALEM, 7, 3, time(20), published_until=date(2026, 10, 1)
    )
    assert behind.published_until == date(2026, 10, 17)


def test_default_horizon_hides_and_blocks_later_classes(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    today = local_today()
    client.patch("/tenants/current", json={"booking_horizon_days": 7}, headers=studio["headers"])
    near = new_session(client, studio, on=today + timedelta(days=2))
    far = new_session(client, studio, on=today + timedelta(days=10))
    user = uuid4()
    member(client, auth, studio, user)
    headers = auth(user, studio["tenant_id"])

    release = client.get("/client/schedule-release", headers=headers).json()
    assert release["published_until"] == (today + timedelta(days=6)).isoformat()
    assert release["next_release_at"] is None and release["booking_horizon_days"] == 7
    listed = client.get(
        "/client/sessions", params={"start": today.isoformat(), "days": 14}, headers=headers
    ).json()
    assert [s["id"] for s in listed] == [near]
    blocked = client.post(f"/client/sessions/{far}/bookings", headers=headers)
    assert (blocked.status_code, blocked.json()["detail"]) == (409, "not_released")
    assert client.post(f"/client/sessions/{near}/bookings", headers=headers).status_code == 201


def test_team_publishes_the_next_week_early(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    today = local_today()
    client.patch("/tenants/current", json={"booking_horizon_days": 7}, headers=studio["headers"])
    far = new_session(client, studio, on=today + timedelta(days=10))
    user = uuid4()
    member(client, auth, studio, user)
    headers = auth(user, studio["tenant_id"])

    forbidden = client.post("/sessions/publish-week", headers=headers)
    assert forbidden.status_code in (401, 403, 404)
    published = client.post("/sessions/publish-week", headers=studio["headers"])
    assert published.json()["published_until"] == (today + timedelta(days=13)).isoformat()
    assert client.post(f"/client/sessions/{far}/bookings", headers=headers).status_code == 201

    for _ in range(2):  # 20 days ahead, then 27; the cap is 28
        client.post("/sessions/publish-week", headers=studio["headers"])
    capped = client.post("/sessions/publish-week", headers=studio["headers"])
    assert (capped.status_code, capped.json()["detail"]) == (409, "already_published")


def test_a_new_business_releases_seven_days(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    created = client.post(
        "/tenants",
        json={
            "name": "Fresh",
            "vertical": "fitness",
            "locale": "he",
            "time_zone": "Asia/Jerusalem",
            "currency": "ILS",
        },
        headers=auth(owner),
    ).json()["id"]

    tenant = client.get("/tenants/current", headers=auth(owner, created)).json()

    assert tenant["booking_horizon_days"] == 7
    assert tenant["weekly_release_weekday"] is None


def test_business_sets_and_clears_the_weekly_release(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]

    saved = client.patch(
        "/tenants/current",
        json={"weekly_release_weekday": 3, "weekly_release_time": "20:00:00"},
        headers=headers,
    ).json()
    assert (saved["weekly_release_weekday"], saved["weekly_release_time"]) == (3, "20:00:00")
    assert saved["booking_horizon_days"] == 60  # the studio fixture's
    half = client.patch("/tenants/current", json={"weekly_release_weekday": 2}, headers=headers)
    assert half.status_code == 422
    assert (
        client.patch("/tenants/current", json={"booking_horizon_days": 0}, headers=headers)
    ).status_code == 422
    cleared = client.patch(
        "/tenants/current",
        json={"weekly_release_weekday": None, "weekly_release_time": None},
        headers=headers,
    ).json()
    assert cleared["weekly_release_weekday"] is None and cleared["weekly_release_time"] is None


def test_class_shows_its_instructor_and_filters_by_them(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    today = local_today()
    day = (today + timedelta(days=2)).isoformat()
    coach = studio["coach"]
    for who in (str(coach), None):
        created = client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": day,
                "start_time": "18:00" if who else "19:00",
                "capacity": 5,
                "instructor_user_id": who,
            },
            headers=studio["headers"],
        )
        assert created.status_code == 201, created.text
    client.patch("/me", json={"full_name": "Coach Dan"}, headers=auth(coach, studio["tenant_id"]))
    client.put(
        "/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth(coach, studio["tenant_id"]),
    )
    user = uuid4()
    member(client, auth, studio, user)
    headers = auth(user, studio["tenant_id"])

    params = {"start": today.isoformat(), "days": 7}
    both = client.get("/client/sessions", params=params, headers=headers).json()
    assert [s["instructor"] is not None for s in both] == [True, False]
    instructor = both[0]["instructor"]
    assert instructor["id"] == str(coach) and instructor["name"] == "Coach Dan"
    assert instructor["avatar_url"].startswith(f"/client/instructors/{coach}/avatar?v=")
    assert "email" not in instructor
    only = client.get(
        "/client/sessions", params={**params, "instructor_id": str(coach)}, headers=headers
    ).json()
    assert [s["id"] for s in only] == [both[0]["id"]]

    picture = client.get(f"/client/instructors/{coach}/avatar", headers=headers)
    assert picture.status_code == 200 and picture.content == PNG
    assert client.get(f"/client/instructors/{uuid4()}/avatar", headers=headers).status_code == 404


def test_instructor_pictures_stay_inside_their_business(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    coach = studio["coach"]
    client.put(
        "/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth(coach, studio["tenant_id"]),
    )
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={
            "name": "Other",
            "vertical": "fitness",
            "locale": "he",
            "time_zone": "Asia/Jerusalem",
            "currency": "ILS",
        },
        headers=auth(other_owner),
    ).json()["id"]
    code = client.get("/tenants/current", headers=auth(other_owner, other)).json()["join_code"]
    user = uuid4()
    client.post("/client/businesses", json={"code": code}, headers=auth(user))

    stolen = client.get(f"/client/instructors/{coach}/avatar", headers=auth(user, other))

    assert stolen.status_code == 404


def test_profile_status_text(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]

    saved = client.patch("/me", json={"status_text": "  Training for a 10K  "}, headers=headers)
    assert saved.json()["status_text"] == "Training for a 10K"
    assert client.get("/me", headers=headers).json()["status_text"] == "Training for a 10K"
    too_long = client.patch("/me", json={"status_text": "x" * 81}, headers=headers)
    assert too_long.status_code == 422
    cleared = client.patch("/me", json={"status_text": "  "}, headers=headers)
    assert cleared.json()["status_text"] is None
