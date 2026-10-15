from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, local_today
from tests.test_bookings import new_session, set_status
from tests.test_client_app import join, member


def person(client: TestClient, auth: AuthHeaders, studio: dict, name: str, **fields: str) -> dict:
    """A client of the studio with an app account, a plan and a signed health form."""
    user = uuid4()
    joined = member(client, auth, studio, user)
    updated = client.patch(
        f"/clients/{joined['client_id']}",
        json={"first_name": name, "last_name": "Cohen", **fields},
        headers=studio["headers"],
    )
    assert updated.status_code == 200, updated.text
    return {"id": joined["client_id"], "headers": auth(user, studio["tenant_id"])}


def befriend(client: TestClient, a: dict, b: dict) -> None:
    code = client.get("/client/friends/settings", headers=b["headers"]).json()["friend_code"]
    sent = client.post("/client/friends/requests", json={"code": code}, headers=a["headers"])
    assert sent.status_code == 201, sent.text
    [incoming] = client.get("/client/friends/requests", headers=b["headers"]).json()["incoming"]
    accepted = client.post(
        f"/client/friends/requests/{incoming['friendship_id']}/accept", headers=b["headers"]
    )
    assert accepted.status_code == 200, accepted.text


def book(client: TestClient, who: dict, session_id: str):
    return client.post(f"/client/sessions/{session_id}/bookings", headers=who["headers"])


def spots_left(client: TestClient, who: dict, session_id: str) -> int:
    start = (local_today() + timedelta(days=15)).isoformat()
    sessions = client.get(
        "/client/sessions", params={"start": start, "days": 14}, headers=who["headers"]
    ).json()
    return next(s["spots_left"] for s in sessions if s["id"] == session_id)


def test_friend_request_by_code_then_accept(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    code = client.get("/client/friends/settings", headers=noa["headers"]).json()["friend_code"]
    assert len(code) == 10
    # The code is stable.
    again = client.get("/client/friends/settings", headers=noa["headers"]).json()["friend_code"]
    assert again == code

    sent = client.post(
        "/client/friends/requests", json={"code": code.lower()}, headers=dana["headers"]
    )
    assert sent.status_code == 201
    assert sent.json()["friendship"] == "request_sent" and sent.json()["last_name"] is None
    again = client.post("/client/friends/requests", json={"code": code}, headers=dana["headers"])
    assert again.status_code == 409 and again.json()["detail"] == "already_requested"

    [incoming] = client.get("/client/friends/requests", headers=noa["headers"]).json()["incoming"]
    assert incoming["first_name"] == "Dana"
    assert client.get("/client/friends", headers=noa["headers"]).json() == []
    # The sender cannot accept their own request.
    own = client.post(
        f"/client/friends/requests/{incoming['friendship_id']}/accept", headers=dana["headers"]
    )
    assert own.status_code == 404

    accepted = client.post(
        f"/client/friends/requests/{incoming['friendship_id']}/accept", headers=noa["headers"]
    )
    assert accepted.status_code == 200 and accepted.json()["last_name"] == "Cohen"
    [friend] = client.get("/client/friends", headers=dana["headers"]).json()
    assert friend["first_name"] == "Noa" and friend["last_name"] == "Cohen"
    assert friend["friends_since"] is not None

    inbox = client.get("/client/notifications", headers=noa["headers"]).json()["items"]
    assert [n["kind"] for n in inbox] == ["friend_request"]
    assert inbox[0]["payload"]["from_name"] == "Dana"

    removed = client.delete(f"/client/friends/{noa['id']}", headers=dana["headers"])
    assert removed.status_code == 204
    assert client.get("/client/friends", headers=noa["headers"]).json() == []


def test_find_by_exact_phone_or_email_only_and_requests_cross(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana", phone="050-123 4567", email="dana@example.com")
    noa = person(client, auth, studio, "Noa", phone="0527654321")

    # +972 and local forms of the same number match; a partial one does not.
    partial = client.post(
        "/client/friends/requests", json={"phone": "0501"}, headers=noa["headers"]
    )
    assert partial.status_code == 404
    unknown = client.post(
        "/client/friends/requests", json={"email": "nobody@example.com"}, headers=noa["headers"]
    )
    assert unknown.status_code == 404
    empty = client.post("/client/friends/requests", json={}, headers=noa["headers"])
    assert empty.status_code == 422

    sent = client.post(
        "/client/friends/requests", json={"phone": "+972 50 123 4567"}, headers=noa["headers"]
    )
    assert sent.status_code == 201 and sent.json()["client_id"] == dana["id"]

    # Dana asking Noa back by email-less phone turns the two requests into a friendship.
    crossed = client.post(
        "/client/friends/requests", json={"phone": "0527654321"}, headers=dana["headers"]
    )
    assert crossed.status_code == 201 and crossed.json()["friendship"] == "friends"
    assert len(client.get("/client/friends", headers=noa["headers"]).json()) == 1
    by_mail = client.post(
        "/client/friends/requests", json={"email": "DANA@example.com"}, headers=noa["headers"]
    )
    assert by_mail.status_code == 409 and by_mail.json()["detail"] == "already_friends"


def test_friends_belong_to_one_business(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    befriend(client, dana, noa)

    # Another business of the same industry has its own, empty friend list.
    owner = uuid4()
    other = client.post("/tenants", json={**STUDIO, "name": "Other"}, headers=auth(owner)).json()
    user = uuid4()
    join(
        client,
        auth,
        user,
        client.get("/tenants/current", headers=auth(owner, other["id"])).json()["join_code"],
    )
    mine = auth(user, other["id"])
    assert client.get("/client/friends", headers=mine).json() == []
    code = client.get("/client/friends/settings", headers=noa["headers"]).json()["friend_code"]
    lost = client.post("/client/friends/requests", json={"code": code}, headers=mine)
    assert lost.status_code == 404


def test_businesses_without_friends_refuse_the_feature(
    client: TestClient, auth: AuthHeaders
) -> None:
    owner = uuid4()
    tenant = client.post(
        "/tenants", json={**STUDIO, "vertical": "beauty"}, headers=auth(owner)
    ).json()
    user = uuid4()
    code = client.get("/tenants/current", headers=auth(owner, tenant["id"])).json()["join_code"]
    join(client, auth, user, code)
    headers = auth(user, tenant["id"])
    assert client.get("/client/friends/settings", headers=headers).json()["enabled"] is False
    for path in ("/client/friends", "/client/friends/requests", "/client/invites"):
        refused = client.get(path, headers=headers)
        assert refused.status_code == 403 and refused.json()["detail"] == "friends_disabled"


def test_invite_holds_a_spot_until_answered(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    gil = person(client, auth, studio, "Gil")
    befriend(client, dana, noa)
    session_id = new_session(client, studio, capacity=2)
    assert book(client, dana, session_id).status_code == 201

    invited = client.post(
        f"/client/sessions/{session_id}/invites",
        json={"friend_id": noa["id"]},
        headers=dana["headers"],
    )
    assert invited.status_code == 201, invited.text
    invite = invited.json()
    assert invite["direction"] == "sent" and invite["other_first_name"] == "Noa"
    # Dana's spot plus the held one: the class is full for everyone else.
    assert spots_left(client, gil, session_id) == 0
    waitlisted = book(client, gil, session_id).json()
    assert waitlisted["my_booking"]["status"] == "waitlisted"

    [received] = client.get("/client/invites", headers=noa["headers"]).json()
    assert received["direction"] == "received" and received["other_first_name"] == "Dana"
    note = client.get("/client/notifications", headers=noa["headers"]).json()["items"][0]
    assert note["kind"] == "class_invite" and note["payload"]["invite_id"] == invite["id"]

    accepted = client.post(f"/client/invites/{invite['id']}/accept", headers=noa["headers"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["my_booking"]["status"] == "booked"
    assert accepted.json()["spots_left"] == 0
    assert client.get("/client/invites", headers=noa["headers"]).json() == []


def test_declined_cancelled_and_expired_invites_free_the_spot(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    befriend(client, dana, noa)
    session_id = new_session(client, studio, capacity=2)
    book(client, dana, session_id)
    path = f"/client/sessions/{session_id}/invites"

    first = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"]).json()
    assert spots_left(client, dana, session_id) == 0
    twice = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"])
    assert twice.status_code == 409
    assert (
        client.post(f"/client/invites/{first['id']}/decline", headers=noa["headers"]).status_code
        == 204
    )
    assert spots_left(client, dana, session_id) == 1

    second = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"]).json()
    assert (
        client.delete(f"/client/invites/{second['id']}", headers=noa["headers"]).status_code == 404
    )
    assert (
        client.delete(f"/client/invites/{second['id']}", headers=dana["headers"]).status_code == 204
    )
    assert spots_left(client, dana, session_id) == 1

    third = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"]).json()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.class_invites SET expires_at = now() - interval '1 minute' "
                "WHERE id = :i"
            ),
            {"i": third["id"]},
        )
    assert spots_left(client, dana, session_id) == 1
    assert client.get("/client/invites", headers=noa["headers"]).json() == []
    late = client.post(f"/client/invites/{third['id']}/accept", headers=noa["headers"])
    assert late.status_code == 409 and late.json()["detail"] == "invite_expired"


def test_invite_rules(client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    gil = person(client, auth, studio, "Gil")
    befriend(client, dana, noa)
    session_id = new_session(client, studio, capacity=1)
    path = f"/client/sessions/{session_id}/invites"

    # I must be in the class myself, and the guest a friend.
    not_booked = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"])
    assert not_booked.status_code == 409 and not_booked.json()["detail"] == "not_booked"
    book(client, dana, session_id)
    stranger = client.post(path, json={"friend_id": gil["id"]}, headers=dana["headers"])
    assert stranger.status_code == 404
    # A full class cannot hold a spot.
    full = client.post(path, json={"friend_id": noa["id"]}, headers=dana["headers"])
    assert full.status_code == 409 and full.json()["detail"] == "session_full"

    roomy = new_session(client, studio, capacity=3, on=local_today() + timedelta(days=21))
    book(client, dana, roomy)
    book(client, noa, roomy)
    already = client.post(
        f"/client/sessions/{roomy}/invites", json={"friend_id": noa["id"]}, headers=dana["headers"]
    )
    assert already.status_code == 409 and already.json()["detail"] == "already_booked"

    # Never later than the class's cancellation deadline: 30 minutes before the start is too late
    # for the default two-hour window.
    soon = new_session(client, studio, capacity=3, on=local_today() + timedelta(days=22))
    book(client, dana, soon)
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = now() + interval '30 minutes',
                                        ends_at = now() + interval '85 minutes'
                WHERE id = :id
            """),
            {"id": soon},
        )
    closed = client.post(
        f"/client/sessions/{soon}/invites", json={"friend_id": noa["id"]}, headers=dana["headers"]
    )
    assert closed.status_code == 409 and closed.json()["detail"] == "invite_window_closed"


def test_the_hold_stops_at_the_cancellation_deadline(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    befriend(client, dana, noa)
    session_id = new_session(client, studio, capacity=3)
    book(client, dana, session_id)
    with engine.begin() as connection:  # starts in 3 hours; the window is 2 hours
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = now() + interval '3 hours',
                                        ends_at = now() + interval '4 hours'
                WHERE id = :id
            """),
            {"id": session_id},
        )
    window = client.get("/tenants/current", headers=studio["headers"]).json()
    invite = client.post(
        f"/client/sessions/{session_id}/invites",
        json={"friend_id": noa["id"]},
        headers=dana["headers"],
    ).json()
    with engine.connect() as connection:
        hold = connection.execute(
            text(
                "SELECT extract(epoch FROM (s.starts_at - i.expires_at)) / 60 "
                "FROM app.class_invites i JOIN app.sessions s ON s.id = i.session_id "
                "WHERE i.id = :i"
            ),
            {"i": invite["id"]},
        ).scalar_one()
    assert float(hold) >= window["cancellation_window_minutes"] - 1


def test_participants_profiles_and_privacy(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    gil = person(client, auth, studio, "Gil")
    session_id = new_session(client, studio, capacity=5)
    for who in (dana, noa, gil):
        book(client, who, session_id)

    seen = client.get(f"/client/sessions/{session_id}/participants", headers=dana["headers"]).json()
    assert {p["first_name"] for p in seen} == {"Noa", "Gil"}
    assert all(p["last_name"] is None and p["friendship"] == "none" for p in seen)
    assert all(set(p) >= {"avatar_url", "status_text", "shared_classes"} for p in seen)
    assert not any("phone" in p or "email" in p for p in seen)

    profile = client.get(f"/client/people/{noa['id']}", headers=dana["headers"])
    assert profile.status_code == 200
    assert profile.json()["last_name"] is None and profile.json()["by_service"] == []

    # Hidden people disappear from the lists and from the profile, unless they are friends.
    hide = client.patch("/client/friends/settings", json={"visible": False}, headers=noa["headers"])
    assert hide.json()["visible"] is False
    seen = client.get(f"/client/sessions/{session_id}/participants", headers=dana["headers"]).json()
    assert [p["first_name"] for p in seen] == ["Gil"]
    assert client.get(f"/client/people/{noa['id']}", headers=dana["headers"]).status_code == 404
    befriend(client, dana, noa)
    seen = client.get(f"/client/sessions/{session_id}/participants", headers=dana["headers"]).json()
    assert [(p["first_name"], p["friendship"]) for p in seen] == [
        ("Noa", "friends"),
        ("Gil", "none"),
    ]

    # A client who is in no class with me and no friend stays invisible.
    other = person(client, auth, studio, "Ron")
    assert client.get(f"/client/people/{other['id']}", headers=dana["headers"]).status_code == 404
    assert (
        client.get(f"/client/people/{other['id']}/avatar", headers=dana["headers"]).status_code
        == 404
    )


def test_shared_classes_are_counted_per_class_type(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    befriend(client, dana, noa)
    first = new_session(client, studio, capacity=5)
    second = new_session(client, studio, capacity=5, on=local_today() + timedelta(days=21))
    for session_id in (first, second):
        book(client, dana, session_id)
        book(client, noa, session_id)
    book_only_dana = new_session(client, studio, capacity=5, on=local_today() + timedelta(days=22))
    book(client, dana, book_only_dana)

    def check_in_all(session_id: str) -> None:
        bookings = client.get(f"/sessions/{session_id}/bookings", headers=studio["headers"]).json()
        for booking in bookings:
            assert (
                set_status(client, studio["headers"], booking["id"], "checked_in").status_code
                == 200
            )

    # Booked together but not yet attended: nothing shared so far.
    profile = client.get(f"/client/people/{noa['id']}", headers=dana["headers"]).json()
    assert profile["shared_classes"] == 0 and profile["by_service"] == []
    check_in_all(first)
    check_in_all(second)
    profile = client.get(f"/client/people/{noa['id']}", headers=dana["headers"]).json()
    assert profile["shared_classes"] == 2
    assert [(s["service_name"], s["shared_classes"]) for s in profile["by_service"]] == [
        ("Pilates", 2)
    ]
    listed = client.get("/client/friends", headers=dana["headers"]).json()
    assert listed[0]["shared_classes"] == 2


def test_clients_cannot_read_friend_tables_of_others(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    dana = person(client, auth, studio, "Dana")
    noa = person(client, auth, studio, "Noa")
    gil = person(client, auth, studio, "Gil")
    befriend(client, dana, noa)
    # Gil's friendship list is empty and a stranger cannot cancel Dana and Noa's friendship.
    assert client.get("/client/friends", headers=gil["headers"]).json() == []
    assert client.delete(f"/client/friends/{noa['id']}", headers=gil["headers"]).status_code == 404
    with engine.connect() as connection:
        friendship = connection.execute(text("SELECT id FROM app.client_friendships")).scalar_one()
    gone = client.delete(
        f"/client/friends/requests/{UUID(str(friendship))}", headers=gil["headers"]
    )
    assert gone.status_code == 404
    assert len(client.get("/client/friends", headers=dana["headers"]).json()) == 1
