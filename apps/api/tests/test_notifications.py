from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_bookings import book, new_session, set_status
from tests.test_client_app import member


def inbox(client: TestClient, headers: dict) -> dict:
    response = client.get("/client/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def app_member(client: TestClient, auth: AuthHeaders, studio: dict) -> tuple[str, dict]:
    user = uuid4()
    joined = member(client, auth, studio, user)
    return joined["client_id"], auth(user, studio["tenant_id"])


def test_waitlist_promotion_notifies_the_promoted_client(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session_id = new_session(client, studio, capacity=1)
    _, alice = app_member(client, auth, studio)
    _, bob = app_member(client, auth, studio)
    booked = client.post(f"/client/sessions/{session_id}/bookings", headers=alice).json()
    client.post(f"/client/sessions/{session_id}/bookings", headers=bob)

    # Alice cancels herself: she gets nothing, Bob moves up and is told.
    client.post(f"/client/bookings/{booked['my_booking']['id']}/cancel", headers=alice)

    assert inbox(client, alice)["items"] == []
    bob_inbox = inbox(client, bob)
    assert bob_inbox["unread"] == 1
    [note] = bob_inbox["items"]
    assert note["kind"] == "waitlist_promoted"
    assert note["payload"]["service_name"] == "Pilates"
    assert note["payload"]["session_id"] == session_id


def test_studio_actions_notify_the_client(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    client_id, headers = app_member(client, auth, studio)
    session_id = new_session(client, studio)

    booking = book(client, studio["headers"], session_id, client_id).json()
    set_status(client, studio["headers"], booking["id"], "cancelled")
    book(client, studio["headers"], session_id, client_id)
    moved = client.patch(
        f"/sessions/{session_id}",
        json={"start_time": "19:30"},
        headers=studio["headers"],
    )
    assert moved.status_code == 200, moved.text
    client.patch(f"/sessions/{session_id}", json={"status": "cancelled"}, headers=studio["headers"])

    kinds = [n["kind"] for n in inbox(client, headers)["items"]]
    assert kinds == [
        "session_cancelled",
        "session_moved",
        "booked_by_studio",
        "booking_cancelled_by_studio",
        "booked_by_studio",
    ]
    moved_note = inbox(client, headers)["items"][1]
    assert moved_note["payload"]["previous_starts_at"] != moved_note["payload"]["starts_at"]


def test_past_sessions_and_unbooked_clients_are_not_notified(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    client_id, headers = app_member(client, auth, studio)
    yesterday = new_session(client, studio, on=local_today() - timedelta(days=1))
    booking = book(client, studio["headers"], yesterday, client_id).json()
    set_status(client, studio["headers"], booking["id"], "no_show")
    other = new_session(client, studio)
    client.patch(f"/sessions/{other}", json={"status": "cancelled"}, headers=studio["headers"])

    assert inbox(client, headers)["items"] == []


def test_health_review_notifies_and_mark_read(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    from tests.test_client_app import sign_health

    _, headers = app_member(client, auth, studio)
    signed = sign_health(client, headers, yes=("heart",))
    client.post(
        f"/health-declarations/{signed['current']['id']}/review",
        json={"approve": True, "note": "Doctor's letter received"},
        headers=studio["headers"],
    )
    session_id = new_session(client, studio)
    client.patch(f"/sessions/{session_id}", json={"capacity": 5}, headers=studio["headers"])

    first = inbox(client, headers)
    [note] = first["items"]
    assert note["kind"] == "health_approved"
    assert note["payload"]["note"] == "Doctor's letter received"
    read = client.post("/client/notifications/read", json={}, headers=headers).json()
    assert read["unread"] == 0 and read["items"][0]["read_at"] is not None


def test_clients_see_only_their_own_notifications(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    alice_id, alice = app_member(client, auth, studio)
    _, bob = app_member(client, auth, studio)
    book(client, studio["headers"], new_session(client, studio), alice_id)
    [note] = inbox(client, alice)["items"]

    assert inbox(client, bob)["items"] == []
    client.post("/client/notifications/read", json={"ids": [note["id"]]}, headers=bob)
    assert inbox(client, alice)["unread"] == 1  # Bob can't mark Alice's notification
