"""Time-off requests: staff ask, a manager decides, an approval blocks the days."""

from datetime import timedelta

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_workspace import at


def test_a_request_is_approved_and_blocks_the_days(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    owner, coach_headers = studio["headers"], auth(studio["coach"], studio["tenant_id"])
    coach = str(studio["coach"])
    day = (local_today() + timedelta(days=1)).isoformat()
    until = (local_today() + timedelta(days=2)).isoformat()
    client.post(
        "/shifts",
        json={
            "user_id": coach,
            "location_id": studio["location"]["id"],
            "starts_at": at(1, 9),
            "ends_at": at(1, 13),
        },
        headers=owner,
    )

    made = client.post(
        "/time-off-requests",
        json={"starts_on": day, "ends_on": until, "reason": " Wedding "},
        headers=coach_headers,
    )
    assert made.status_code == 201
    request = made.json()
    assert request["status"] == "pending" and request["reason"] == "Wedding"
    assert request["shift_count"] == 1
    # Overlapping a request that is still open is refused.
    again = client.post(
        "/time-off-requests", json={"starts_on": until, "ends_on": until}, headers=coach_headers
    )
    assert again.status_code == 409 and again.json()["detail"] == "request_overlap"

    # Staff cannot decide; they see only their own; the owner sees the pending one.
    assert (
        client.post(
            f"/time-off-requests/{request['id']}/approve", json={}, headers=coach_headers
        ).status_code
        == 403
    )
    assert len(client.get("/time-off-requests", headers=coach_headers).json()) == 1
    queue = client.get("/time-off-requests", params={"status": "pending"}, headers=owner).json()
    assert [r["id"] for r in queue] == [request["id"]]

    approved = client.post(
        f"/time-off-requests/{request['id']}/approve", json={"note": "Enjoy"}, headers=owner
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert approved.json()["decision_note"] == "Enjoy"
    away = client.get(f"/staff/{coach}/time-off", headers=owner).json()
    assert [(a["starts_on"], a["ends_on"]) for a in away] == [(day, until)]
    on_board = client.get("/shifts", params={"start": day, "days": 1}, headers=owner).json()
    assert on_board[0]["on_time_off"] is True
    # Decided once; the requester cannot withdraw it any more.
    twice = client.post(f"/time-off-requests/{request['id']}/decline", json={}, headers=owner)
    assert twice.status_code == 409 and twice.json()["detail"] == "request_not_pending"
    assert (
        client.delete(f"/time-off-requests/{request['id']}", headers=coach_headers).status_code
        == 404
    )


def test_a_request_can_be_declined_or_withdrawn(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    owner, coach_headers = studio["headers"], auth(studio["coach"], studio["tenant_id"])
    coach = str(studio["coach"])
    day = (local_today() + timedelta(days=5)).isoformat()
    first = client.post(
        "/time-off-requests", json={"starts_on": day, "ends_on": day}, headers=coach_headers
    ).json()
    declined = client.post(
        f"/time-off-requests/{first['id']}/decline", json={"note": "Busy day"}, headers=owner
    ).json()
    assert declined["status"] == "declined" and declined["decision_note"] == "Busy day"
    assert client.get(f"/staff/{coach}/time-off", headers=owner).json() == []

    # After a decline the same days can be asked again, and a pending one can be withdrawn.
    second = client.post(
        "/time-off-requests", json={"starts_on": day, "ends_on": day}, headers=coach_headers
    ).json()
    assert (
        client.delete(f"/time-off-requests/{second['id']}", headers=coach_headers).status_code
        == 204
    )
    mine = client.get("/time-off-requests", params={"mine": True}, headers=owner).json()
    assert mine == []
    # Nobody asks for days that are over.
    past = (local_today() - timedelta(days=3)).isoformat()
    late = client.post(
        "/time-off-requests", json={"starts_on": past, "ends_on": past}, headers=coach_headers
    )
    assert late.status_code == 422
