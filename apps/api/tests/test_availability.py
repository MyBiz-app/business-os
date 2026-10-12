"""Shift availability and coverage: staff say when they can work, the board shows the gaps."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_workspace import at


def _weekday(offset: int) -> int:
    return (local_today() + timedelta(days=offset)).weekday()


def test_a_person_sets_their_own_week_and_a_manager_sees_it(
    client: TestClient, auth: AuthHeaders, studio: dict, engine: Engine
) -> None:
    owner, tenant, coach = studio["headers"], studio["tenant_id"], studio["coach"]
    coach_h = auth(coach, tenant)
    assert client.get("/me/availability", headers=coach_h).json() == {"windows": []}

    overlapping = {
        "windows": [
            {"weekday": 0, "starts": "08:00", "ends": "12:00"},
            {"weekday": 0, "starts": "11:00", "ends": "14:00"},
        ]
    }
    assert client.put("/me/availability", json=overlapping, headers=coach_h).status_code == 422
    backwards = {"windows": [{"weekday": 0, "starts": "12:00", "ends": "08:00"}]}
    assert client.put("/me/availability", json=backwards, headers=coach_h).status_code == 422

    week = {
        "windows": [
            {"weekday": 2, "starts": "16:00", "ends": "20:00"},
            {"weekday": 0, "starts": "08:00", "ends": "12:00"},
        ]
    }
    saved = client.put("/me/availability", json=week, headers=coach_h)
    assert saved.status_code == 200
    assert [w["weekday"] for w in saved.json()["windows"]] == [0, 2]

    # Staff cannot read or set someone else's week; a manager can.
    assert client.get(f"/staff/{coach}/availability", headers=coach_h).status_code == 403
    assert client.get("/shifts/availability", headers=coach_h).status_code == 403
    assert len(client.get(f"/staff/{coach}/availability", headers=owner).json()["windows"]) == 2
    board = client.get("/shifts/availability", headers=owner).json()
    assert [p["user_id"] for p in board] == [str(coach)]
    assert client.get(f"/staff/{uuid4()}/availability", headers=owner).status_code == 404

    cleared = client.put(f"/staff/{coach}/availability", json={"windows": []}, headers=owner)
    assert cleared.json() == {"windows": []}
    assert client.get("/shifts/availability", headers=owner).json() == []

    # Another business never sees it.
    other = uuid4()
    add_member(engine, tenant, other, "staff")
    assert client.get("/me/availability", headers=auth(other, tenant)).json() == {"windows": []}


def test_a_shift_outside_availability_is_flagged(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    owner, branch, coach = studio["headers"], studio["location"]["id"], str(studio["coach"])
    shift = {"user_id": coach, "location_id": branch, "starts_at": at(1, 9), "ends_at": at(1, 12)}
    created = client.post("/shifts", json=shift, headers=owner).json()
    assert created["outside_availability"] is False  # not said: no warning

    client.put(
        f"/staff/{coach}/availability",
        json={"windows": [{"weekday": _weekday(1), "starts": "08:00", "ends": "11:00"}]},
        headers=owner,
    )
    listed = client.get(
        "/shifts", params={"start": local_today().isoformat()}, headers=owner
    ).json()
    assert [s["outside_availability"] for s in listed] == [True]
    fixed = client.patch(f"/shifts/{created['id']}", json={"ends_at": at(1, 11)}, headers=owner)
    assert fixed.json()["outside_availability"] is False

    # Past midnight: the evening up to 23:59 and the next morning from 00:00.
    night = {**shift, "starts_at": at(2, 22), "ends_at": at(3, 2)}
    client.put(
        f"/staff/{coach}/availability",
        json={
            "windows": [
                {"weekday": _weekday(2), "starts": "20:00", "ends": "23:59"},
                {"weekday": _weekday(3), "starts": "00:00", "ends": "03:00"},
            ]
        },
        headers=owner,
    )
    assert client.post("/shifts", json=night, headers=owner).json()["outside_availability"] is False


def test_coverage_gaps_can_use_the_published_roster_and_suggest_who_can_cover(
    client: TestClient, auth: AuthHeaders, studio: dict, engine: Engine
) -> None:
    owner, tenant, branch = studio["headers"], studio["tenant_id"], studio["location"]["id"]
    coach, helper, away, busy = str(studio["coach"]), uuid4(), uuid4(), uuid4()
    for person in (helper, away, busy):
        add_member(engine, tenant, person, "staff")
    day = local_today() + timedelta(days=1)
    rule = {"weekday": day.weekday(), "starts_minute": 8 * 60, "ends_minute": 12 * 60}
    client.put(
        f"/locations/{branch}/coverage-rules",
        json={"rules": [{**rule, "min_staff": 1}]},
        headers=owner,
    )
    # A draft shift covers the morning; the published roster is still empty.
    client.post(
        "/shifts",
        json={"user_id": coach, "location_id": branch, "starts_at": at(1, 8), "ends_at": at(1, 12)},
        headers=owner,
    )
    params = {"start": day.isoformat(), "days": 1}
    assert client.get("/shifts/coverage", params=params, headers=owner).json() == []
    published = client.get(
        "/shifts/coverage", params={**params, "published_only": True}, headers=owner
    ).json()
    assert [(g["starts_minute"], g["ends_minute"], g["have"]) for g in published] == [(480, 720, 0)]
    assert published[0]["available"] == []  # nobody said when they can work

    # Who can cover: said they can work the whole stretch, not away, not already working.
    window = {"windows": [{"weekday": day.weekday(), "starts": "07:00", "ends": "13:00"}]}
    for person in (helper, away, busy):
        client.put(f"/staff/{person}/availability", json=window, headers=owner)
    short = {"windows": [{"weekday": day.weekday(), "starts": "09:00", "ends": "13:00"}]}
    client.put(f"/staff/{coach}/availability", json=short, headers=owner)
    client.post(
        f"/staff/{away}/time-off",
        json={"starts_on": day.isoformat(), "ends_on": day.isoformat()},
        headers=owner,
    )
    other = client.post("/locations", json={"name": "Second"}, headers=owner).json()
    client.post(
        "/shifts",
        json={
            "user_id": str(busy),
            "location_id": other["id"],
            "starts_at": at(1, 10),
            "ends_at": at(1, 11),
        },
        headers=owner,
    )
    gaps = client.get(
        "/shifts/coverage", params={**params, "published_only": True}, headers=owner
    ).json()
    assert [c["user_id"] for c in gaps[0]["available"]] == [str(helper)]

    # Staff see the gaps (as before) but not who could cover.
    coach_h = auth(studio["coach"], tenant)
    seen = client.get(
        "/shifts/coverage", params={**params, "published_only": True}, headers=coach_h
    ).json()
    assert len(seen) == 1 and seen[0]["available"] == []
