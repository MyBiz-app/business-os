"""Shift swaps: offer, colleague accepts, manager approves, the shift changes hands."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_workspace import at


def _published_shift(client: TestClient, studio: dict, person) -> str:
    shift = client.post(
        "/shifts",
        json={
            "user_id": str(person),
            "location_id": studio["location"]["id"],
            "starts_at": at(2, 9),
            "ends_at": at(2, 13),
        },
        headers=studio["headers"],
    ).json()
    client.post(
        "/shifts/publish", json={"start": local_today().isoformat()}, headers=studio["headers"]
    )
    return shift["id"]


def test_a_swap_goes_colleague_then_manager_then_the_shift_moves(
    client: TestClient, auth: AuthHeaders, studio: dict, engine: Engine
) -> None:
    owner, tenant = studio["headers"], studio["tenant_id"]
    coach, friend, other = studio["coach"], uuid4(), uuid4()
    add_member(engine, tenant, friend, "staff")
    add_member(engine, tenant, other, "staff")
    coach_h, friend_h, other_h = auth(coach, tenant), auth(friend, tenant), auth(other, tenant)
    shift_id = _published_shift(client, studio, coach)

    # Only the owner of the shift can offer it, and not to themselves.
    assert (
        client.post(
            "/shift-swaps", json={"shift_id": shift_id, "to_user_id": str(coach)}, headers=coach_h
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/shift-swaps", json={"shift_id": shift_id, "to_user_id": str(coach)}, headers=other_h
        ).status_code
        == 404
    )
    made = client.post(
        "/shift-swaps",
        json={"shift_id": shift_id, "to_user_id": str(friend), "note": " Dentist "},
        headers=coach_h,
    )
    assert made.status_code == 201
    swap = made.json()
    assert swap["status"] == "pending_colleague" and swap["note"] == "Dentist"
    # One open swap per shift.
    dup = client.post(
        "/shift-swaps", json={"shift_id": shift_id, "to_user_id": str(other)}, headers=coach_h
    )
    assert dup.status_code == 409 and dup.json()["detail"] == "swap_open"

    # Visibility: the two people and the owner; not a bystander.
    assert len(client.get("/shift-swaps", headers=friend_h).json()) == 1
    assert client.get("/shift-swaps", headers=other_h).json() == []
    assert len(client.get("/shift-swaps", headers=owner).json()) == 1

    # Only the colleague answers; a manager cannot approve before that.
    base = f"/shift-swaps/{swap['id']}"
    assert client.post(f"{base}/accept", headers=coach_h).status_code == 404
    early = client.post(f"{base}/approve", json={}, headers=owner)
    assert early.status_code == 409 and early.json()["detail"] == "swap_not_pending"
    accepted = client.post(f"{base}/accept", headers=friend_h)
    assert accepted.json()["status"] == "pending_manager"
    assert client.post(f"{base}/approve", json={}, headers=friend_h).status_code == 403

    approved = client.post(f"{base}/approve", json={"note": "Thanks"}, headers=owner)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    on_board = client.get(
        "/shifts", params={"start": local_today().isoformat(), "days": 7}, headers=owner
    ).json()
    assert [s["user_id"] for s in on_board if s["id"] == shift_id] == [str(friend)]
    # Decided once; the offer can no longer be withdrawn.
    assert client.delete(base, headers=coach_h).status_code in (404, 409)


def test_refused_declined_and_cancelled_swaps_leave_the_shift_alone(
    client: TestClient, auth: AuthHeaders, studio: dict, engine: Engine
) -> None:
    owner, tenant, coach, friend = studio["headers"], studio["tenant_id"], studio["coach"], uuid4()
    add_member(engine, tenant, friend, "staff")
    coach_h, friend_h = auth(coach, tenant), auth(friend, tenant)
    shift_id = _published_shift(client, studio, coach)

    def offer() -> str:
        return client.post(
            "/shift-swaps", json={"shift_id": shift_id, "to_user_id": str(friend)}, headers=coach_h
        ).json()["id"]

    first = offer()
    assert (
        client.post(f"/shift-swaps/{first}/refuse", headers=friend_h).json()["status"] == "refused"
    )
    second = offer()
    client.post(f"/shift-swaps/{second}/accept", headers=friend_h)
    declined = client.post(
        f"/shift-swaps/{second}/decline", json={"note": "Short-staffed"}, headers=owner
    )
    assert (
        declined.json()["status"] == "declined"
        and declined.json()["decision_note"] == "Short-staffed"
    )
    third = offer()
    assert client.delete(f"/shift-swaps/{third}", headers=coach_h).status_code == 204
    assert client.delete(f"/shift-swaps/{third}", headers=coach_h).status_code == 409
    shifts = client.get(
        "/shifts", params={"start": local_today().isoformat()}, headers=owner
    ).json()
    assert [s["user_id"] for s in shifts if s["id"] == shift_id] == [str(coach)]


def test_approval_fails_if_the_colleague_is_busy_then(
    client: TestClient, auth: AuthHeaders, studio: dict, engine: Engine
) -> None:
    owner, tenant, coach, friend = studio["headers"], studio["tenant_id"], studio["coach"], uuid4()
    add_member(engine, tenant, friend, "staff")
    coach_h, friend_h = auth(coach, tenant), auth(friend, tenant)
    shift_id = _published_shift(client, studio, coach)
    swap = client.post(
        "/shift-swaps", json={"shift_id": shift_id, "to_user_id": str(friend)}, headers=coach_h
    ).json()
    client.post(f"/shift-swaps/{swap['id']}/accept", headers=friend_h)
    client.post(
        "/shifts",
        json={
            "user_id": str(friend),
            "location_id": studio["location"]["id"],
            "starts_at": at(2, 11),
            "ends_at": at(2, 15),
        },
        headers=owner,
    )
    clash = client.post(f"/shift-swaps/{swap['id']}/approve", json={}, headers=owner)
    assert clash.status_code == 409 and clash.json()["detail"] == "shift_overlap"
