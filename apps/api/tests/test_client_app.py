from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, local_today
from tests.test_bookings import book, new_client, new_session


def join_code(client: TestClient, studio: dict) -> str:
    return client.get("/tenants/current", headers=studio["headers"]).json()["join_code"]


def join(client: TestClient, auth: AuthHeaders, user: UUID, code: str) -> dict:
    response = client.post("/client/businesses", json={"code": code}, headers=auth(user))
    assert response.status_code == 201, response.text
    return response.json()


def give_plan(client: TestClient, studio: dict, client_id: str, name: str = "Monthly") -> dict:
    """Sells the business's unlimited membership (a default plan of the fitness pack)."""
    plans = client.get("/plans", headers=studio["headers"]).json()
    membership = next(p for p in plans if p["kind"] == "membership")
    sold = client.post(
        f"/clients/{client_id}/entitlements",
        json={"plan_id": membership["id"], "idempotency_key": f"sale-{uuid4()}"},
        headers=studio["headers"],
    )
    assert sold.status_code == 201, sold.text
    return sold.json()


def member(client: TestClient, auth: AuthHeaders, studio: dict, user: UUID) -> dict:
    """A client who joined through the app and holds a membership."""
    joined = join(client, auth, user, join_code(client, studio))
    give_plan(client, studio, joined["client_id"])
    return joined


def upcoming(client: TestClient, headers: dict) -> list:
    start = (local_today() + timedelta(days=15)).isoformat()  # new_session() is 20 days out
    response = client.get("/client/sessions", params={"start": start, "days": 14}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_public_profile_by_join_code(client: TestClient, studio: dict) -> None:
    code = join_code(client, studio)

    profile = client.get(f"/public/businesses/{code.lower()}")

    assert profile.status_code == 200
    assert profile.json()["name"] == STUDIO["name"]
    assert set(profile.json()) == {
        "id",
        "name",
        "locale",
        "primary_color",
        "logo_url",
        "client_app",
    }
    assert client.get("/public/businesses/NOPE2345").status_code == 404


def test_join_creates_client_once_and_lists_business(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    code = join_code(client, studio)

    first = join(client, auth, user, code)
    again = join(client, auth, user, f" {code.lower()} ")

    assert first["client_id"] == again["client_id"]
    assert first["first_name"] == str(user)  # local part of <user>@example.com
    assert [b["id"] for b in client.get("/client/businesses", headers=auth(user)).json()] == [
        str(studio["tenant_id"])
    ]
    members = client.get("/clients", headers=studio["headers"]).json()
    assert members["total"] == 1
    unknown = client.post("/client/businesses", json={"code": "NOPE2345"}, headers=auth(user))
    assert unknown.status_code == 404


def test_join_claims_existing_client_with_same_email(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    existing = client.post(
        "/clients",
        json={"first_name": "Dana", "email": f"{user}@EXAMPLE.com"},
        headers=studio["headers"],
    ).json()

    joined = join(client, auth, user, join_code(client, studio))

    assert joined["client_id"] == existing["id"]
    assert joined["first_name"] == "Dana"


def test_client_books_sees_spots_and_cancels(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session_id = new_session(client, studio, capacity=1)
    alice, bob = uuid4(), uuid4()
    member(client, auth, studio, alice)
    member(client, auth, studio, bob)
    alice_headers = auth(alice, studio["tenant_id"])
    bob_headers = auth(bob, studio["tenant_id"])

    [listed] = upcoming(client, alice_headers)
    assert listed["spots_left"] == 1 and listed["my_booking"] is None

    booked = client.post(f"/client/sessions/{session_id}/bookings", headers=alice_headers)
    assert booked.status_code == 201
    assert booked.json()["my_booking"]["status"] == "booked"
    assert booked.json()["spots_left"] == 0

    waiting = client.post(f"/client/sessions/{session_id}/bookings", headers=bob_headers).json()
    assert waiting["my_booking"]["status"] == "waitlisted"
    assert waiting["my_booking"]["waitlist_position"] == 1
    again = client.post(f"/client/sessions/{session_id}/bookings", headers=bob_headers)
    assert again.status_code == 409

    alice_booking = booked.json()["my_booking"]["id"]
    cancelled = client.post(f"/client/bookings/{alice_booking}/cancel", headers=alice_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["my_booking"] is None

    [bob_view] = upcoming(client, bob_headers)
    assert bob_view["my_booking"]["status"] == "booked"  # promoted from the waitlist
    history = client.get("/client/bookings", headers=alice_headers).json()
    assert [b["status"] for b in history] == ["cancelled"]


def test_client_cannot_book_started_sessions(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    session_id = new_session(client, studio)
    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.sessions SET starts_at = now() - interval '1 minute' WHERE id = :id"),
            {"id": session_id},
        )

    response = client.post(
        f"/client/sessions/{session_id}/bookings", headers=auth(user, studio["tenant_id"])
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "session_started"


def test_client_sees_only_own_data(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    session_id = new_session(client, studio)
    dana = new_client(client, studio["headers"], "Dana")
    staff_booking = book(client, studio["headers"], session_id, dana).json()
    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    headers = auth(user, studio["tenant_id"])

    # Client endpoints only; staff endpoints refuse a non-member.
    assert client.get("/clients", headers=headers).status_code == 403
    assert client.get(f"/sessions/{session_id}/bookings", headers=headers).status_code == 403
    cancel_other = client.post(f"/client/bookings/{staff_booking['id']}/cancel", headers=headers)
    assert cancel_other.status_code == 404
    [listed] = upcoming(client, headers)
    assert listed["spots_left"] == 1  # capacity 2, Dana holds one: counts include others


def test_client_endpoints_require_joining(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    stranger = uuid4()
    headers = auth(stranger, studio["tenant_id"])

    response = client.get("/client/sessions", params={"start": "2026-10-11"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "not_a_client"


def test_client_of_one_business_cannot_reach_another(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    other_owner = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]

    response = client.get(
        "/client/sessions", params={"start": "2026-10-11"}, headers=auth(user, other)
    )

    assert response.status_code == 403
    assert len(client.get("/client/businesses", headers=auth(user)).json()) == 1


def test_late_window_applies_to_clients(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    soon = local_today() + timedelta(days=1)
    session_id = new_session(client, studio, on=soon)
    user = uuid4()
    member(client, auth, studio, user)
    headers = auth(user, studio["tenant_id"])
    booking = client.post(f"/client/sessions/{session_id}/bookings", headers=headers).json()
    with engine.begin() as connection:  # starts in 30 minutes, inside the 2 h window
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = now() + interval '30 minutes',
                                        ends_at = now() + interval '85 minutes'
                WHERE id = :id
            """),
            {"id": session_id},
        )

    client.post(f"/client/bookings/{booking['my_booking']['id']}/cancel", headers=headers)

    [entry] = client.get("/client/bookings", headers=headers).json()
    assert entry["late_cancel"] is True


def test_client_needs_a_valid_plan(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    session_id = new_session(client, studio)
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    headers = auth(user, studio["tenant_id"])

    refused = client.post(f"/client/sessions/{session_id}/bookings", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "no_valid_plan"
    assert len(client.get("/client/plans", headers=headers).json()) == 3  # pack defaults

    give_plan(client, studio, joined["client_id"])
    booked = client.post(f"/client/sessions/{session_id}/bookings", headers=headers)
    assert booked.status_code == 201
    [mine] = client.get("/client/entitlements", headers=headers).json()
    assert mine["state"] == "active" and mine["credits_used"] == 1
