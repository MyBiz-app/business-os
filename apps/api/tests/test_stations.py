"""Stations: shifts planned into named rooms of a branch, several people to one room."""

from datetime import timedelta

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_workspace import at


def test_shifts_are_planned_into_stations_of_their_branch(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers, branch, coach = studio["headers"], studio["location"]["id"], str(studio["coach"])
    owner = str(studio["owner"])
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    pilates = client.post(
        "/stations", json={"location_id": branch, "name": " Pilates 1 "}, headers=headers
    )
    assert pilates.status_code == 201 and pilates.json()["name"] == "Pilates 1"
    pilates_id = pilates.json()["id"]
    yoga_id = client.post(
        "/stations", json={"location_id": branch, "name": "Yoga 2"}, headers=headers
    ).json()["id"]
    elsewhere = client.post(
        "/stations", json={"location_id": south, "name": "Hall"}, headers=headers
    ).json()["id"]
    dup = client.post(
        "/stations", json={"location_id": branch, "name": "pilates 1"}, headers=headers
    )
    assert dup.status_code == 409 and dup.json()["detail"] == "station_name_taken"
    listed = client.get("/stations", params={"location_id": branch}, headers=headers).json()
    assert [s["name"] for s in listed] == ["Pilates 1", "Yoga 2"]

    shift = {"location_id": branch, "starts_at": at(1, 9), "ends_at": at(1, 13)}
    # Two people may share one station at the same time.
    first = client.post(
        "/shifts", json={**shift, "user_id": coach, "station_id": pilates_id}, headers=headers
    )
    second = client.post(
        "/shifts", json={**shift, "user_id": owner, "station_id": pilates_id}, headers=headers
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["station_name"] == "Pilates 1"
    # A station of another branch is refused; so is moving a shift to that branch with it.
    wrong = client.post(
        "/shifts",
        json={**shift, "user_id": coach, "starts_at": at(2, 9), "ends_at": at(2, 12)}
        | {"station_id": elsewhere},
        headers=headers,
    )
    assert wrong.status_code == 422
    # Changing the station, clearing it, and moving branches (which clears it).
    shift_id = first.json()["id"]
    moved = client.patch(f"/shifts/{shift_id}", json={"station_id": yoga_id}, headers=headers)
    assert moved.json()["station_name"] == "Yoga 2"
    note = client.patch(f"/shifts/{shift_id}", json={"note": "Opens"}, headers=headers)
    assert note.json()["station_id"] == yoga_id
    cleared = client.patch(f"/shifts/{shift_id}", json={"station_id": None}, headers=headers)
    assert cleared.json()["station_id"] is None
    client.patch(f"/shifts/{shift_id}", json={"station_id": yoga_id}, headers=headers)
    away = client.patch(f"/shifts/{shift_id}", json={"location_id": south}, headers=headers)
    assert away.status_code == 200 and away.json()["station_id"] is None

    # Copying a day keeps the stations.
    today = local_today()
    client.post(
        "/shifts/copy-day",
        json={
            "from_day": (today + timedelta(days=1)).isoformat(),
            "to_days": [(today + timedelta(days=3)).isoformat()],
        },
        headers=headers,
    )
    copied = client.get(
        "/shifts",
        params={"start": (today + timedelta(days=3)).isoformat(), "days": 1},
        headers=headers,
    ).json()
    assert sorted(s["station_name"] or "" for s in copied) == ["", "Pilates 1"]

    # Renaming, and deleting a station only clears it from its shifts.
    renamed = client.patch(f"/stations/{pilates_id}", json={"name": "Pilates A"}, headers=headers)
    assert renamed.json()["name"] == "Pilates A"
    assert client.delete(f"/stations/{pilates_id}", headers=headers).status_code == 204
    left = client.get(
        "/shifts",
        params={"start": (today + timedelta(days=1)).isoformat(), "days": 1},
        headers=headers,
    ).json()
    assert len(left) == 2 and all(
        s["station_id"] is None or s["station_id"] == yoga_id for s in left
    )

    # The team reads stations; only managers define them.
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/stations", headers=coach_headers).status_code == 200
    body = {"location_id": branch, "name": "Spin"}
    assert client.post("/stations", json=body, headers=coach_headers).status_code == 403
