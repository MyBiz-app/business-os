"""The smart waitlist (round 7, R30): requests for a range or a whole day, the three modes,
the cut-off before a class, claiming a spot, and who is told when."""

from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_appointments import at, barber  # noqa: F401 (fixture)
from tests.test_bookings import new_session
from tests.test_client_app import join, join_code, member
from tests.test_resources import club, club_member  # noqa: F401 (fixture)

TZ = ZoneInfo("Asia/Jerusalem")


def set_waitlist(client: TestClient, headers: dict, **fields: object) -> None:
    changed = client.patch("/tenants/current", json=fields, headers=headers)
    assert changed.status_code == 200, changed.text


def kinds(client: TestClient, headers: dict) -> list[str]:
    response = client.get("/client/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return [n["kind"] for n in response.json()["items"]]


def app_clients(client: TestClient, auth: AuthHeaders, studio: dict, count: int) -> list[dict]:
    people = []
    for _ in range(count):
        user = uuid4()
        member(client, auth, studio, user)
        people.append({"user": user, "headers": auth(user, studio["tenant_id"])})
    return people


def full_class(client: TestClient, auth: AuthHeaders, studio: dict, names: int = 3, **kw):
    """A class of one spot: the first app client holds it, the others queue."""
    session_id = new_session(client, studio, capacity=1, on=kw.get("on"))
    people = app_clients(client, auth, studio, names)
    bookings = []
    for person in people:
        response = client.post(f"/client/sessions/{session_id}/bookings", headers=person["headers"])
        assert response.status_code == 201, response.text
        bookings.append(response.json()["my_booking"])
    return session_id, people, bookings


def test_settings_and_the_pack_defaults(client: TestClient, studio: dict, barber: dict) -> None:  # noqa: F811
    fitness = client.get("/tenants/current", headers=studio["headers"]).json()
    assert fitness["waitlist_enabled"] is True
    assert fitness["waitlist_class_mode"] == "auto"
    assert fitness["waitlist_appointment_mode"] == "first_come"
    assert fitness["waitlist_resource_mode"] == "first_come"
    assert fitness["waitlist_auto_hours"] == 3
    beauty = client.get("/tenants/current", headers=barber["headers"]).json()
    assert beauty["waitlist_class_mode"] == "first_come"
    assert beauty["waitlist_resource_mode"] == "off"

    set_waitlist(client, studio["headers"], waitlist_class_mode="manual", waitlist_auto_hours=6)
    again = client.get("/tenants/current", headers=studio["headers"]).json()
    assert again["waitlist_class_mode"] == "manual" and again["waitlist_auto_hours"] == 6
    bad = client.patch(
        "/tenants/current", json={"waitlist_class_mode": "whenever"}, headers=studio["headers"]
    )
    assert bad.status_code == 422


def test_auto_mode_promotes_a_class_far_ahead_and_offers_it_close_in(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    # 20 days ahead: the first in line is signed in, as before.
    _, people, bookings = full_class(client, auth, studio, names=3)
    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])
    assert "waitlist_promoted" in kinds(client, people[1]["headers"])
    assert "waitlist_spot_open" not in kinds(client, people[2]["headers"])

    # Tomorrow with a 72 hour cut-off: too close for that, so the spot is offered instead.
    set_waitlist(client, studio["headers"], waitlist_auto_hours=72)
    soon, people, bookings = full_class(
        client, auth, studio, names=3, on=local_today() + timedelta(days=1)
    )
    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])

    waiting = client.get("/client/waitlist", headers=people[1]["headers"]).json()
    assert [w["offer_session_id"] for w in waiting] == [soon]
    assert "waitlist_spot_open" in kinds(client, people[1]["headers"])
    assert "waitlist_spot_open" in kinds(client, people[2]["headers"])
    roster = client.get(f"/sessions/{soon}/bookings", headers=studio["headers"]).json()
    assert [b["status"] for b in roster].count("waitlisted") == 2  # nobody was signed in


def test_first_to_take_it_gets_it_and_the_others_are_told(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    set_waitlist(client, studio["headers"], waitlist_class_mode="first_come")
    session_id, people, bookings = full_class(client, auth, studio, names=3)
    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])
    second, third = people[1]["headers"], people[2]["headers"]

    first = client.post("/client/waitlist/claim", json={"session_id": session_id}, headers=third)
    late = client.post("/client/waitlist/claim", json={"session_id": session_id}, headers=second)

    assert first.status_code == 201, first.text
    assert late.status_code == 409 and late.json()["detail"] == "spot_taken"
    assert "waitlist_spot_taken" in kinds(client, second)
    assert "waitlist_spot_taken" not in kinds(client, third)
    roster = client.get(f"/sessions/{session_id}/bookings", headers=studio["headers"]).json()
    live = {b["client_name"]: b["status"] for b in roster if b["status"] != "cancelled"}
    assert sorted(live.values()) == ["booked", "waitlisted"]
    # Still waiting, with no spot to take.
    [still] = client.get("/client/waitlist", headers=second).json()
    assert still["source"] == "booking" and still["offer_session_id"] is None


def test_manual_mode_tells_nobody_and_the_team_lets_someone_in(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    set_waitlist(client, studio["headers"], waitlist_class_mode="manual")
    session_id, people, bookings = full_class(client, auth, studio, names=3)
    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])

    assert "waitlist_spot_open" not in kinds(client, people[1]["headers"])
    listed = client.get("/waitlist", headers=studio["headers"]).json()
    assert [e["mode"] for e in listed] == ["manual", "manual"]
    assert [e["open_session_id"] for e in listed] == [session_id, session_id]
    assert [e["position"] for e in listed] == [1, 2]

    admitted = client.post(f"/waitlist/bookings/{listed[1]['id']}/admit", headers=studio["headers"])
    assert admitted.status_code == 200, admitted.text
    # The spot is gone, so the other waiting entry has nothing to be let into any more.
    after = client.get("/waitlist", headers=studio["headers"]).json()
    assert [e["open_session_id"] for e in after] == [None]
    again = client.post(f"/waitlist/bookings/{after[0]['id']}/admit", headers=studio["headers"])
    assert again.status_code == 409 and again.json()["detail"] == "spot_taken"
    assert "booked_by_studio" in kinds(client, people[2]["headers"])


def test_a_range_request_is_offered_a_matching_class_only(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session_id, people, bookings = full_class(client, auth, studio, names=1)
    asker, rival = (p["headers"] for p in app_clients(client, auth, studio, 2))
    day = (local_today() + timedelta(days=20)).isoformat()
    service = studio["service"]["id"]
    elsewhere = client.post(
        "/client/waitlist",
        json={"service_id": service, "kind": "range", "day": day,
              "from_time": "08:00", "to_time": "12:00"},
        headers=asker,
    )  # fmt: skip
    evening = client.post(
        "/client/waitlist",
        json={"service_id": service, "kind": "range", "day": day,
              "from_time": "17:00", "to_time": "19:00"},
        headers=asker,
    )  # fmt: skip
    assert elsewhere.status_code == 201 and evening.status_code == 201, evening.text

    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])
    # The cancelling client's own app never sees other clients' requests, yet the asker is told.
    mine = {w["id"]: w for w in client.get("/client/waitlist", headers=asker).json()}
    assert mine[evening.json()["id"]]["offer_session_id"] == session_id
    assert mine[elsewhere.json()["id"]]["offer_session_id"] is None
    assert kinds(client, asker).count("waitlist_spot_open") == 1

    # Someone books the free spot in the normal way before the asker taps: it is gone for them.
    rival_booked = client.post(f"/client/sessions/{session_id}/bookings", headers=rival)
    assert rival_booked.json()["my_booking"]["status"] == "booked"
    assert "waitlist_spot_taken" in kinds(client, asker)
    taken = client.post("/client/waitlist/claim", json={"session_id": session_id}, headers=asker)
    assert taken.status_code == 409 and taken.json()["detail"] == "spot_taken"
    left = {w["id"]: w for w in client.get("/client/waitlist", headers=asker).json()}
    assert left[evening.json()["id"]]["offer_session_id"] is None


def test_a_whole_day_request_claims_a_freed_class(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session_id = new_session(client, studio, capacity=1)
    people = app_clients(client, auth, studio, 2)
    holder, asker = people[0]["headers"], people[1]["headers"]
    held = client.post(f"/client/sessions/{session_id}/bookings", headers=holder).json()
    day = (local_today() + timedelta(days=20)).isoformat()
    request = client.post(
        "/client/waitlist",
        json={"service_id": studio["service"]["id"], "kind": "day", "day": day},
        headers=asker,
    )
    assert request.status_code == 201, request.text

    client.post(f"/client/bookings/{held['my_booking']['id']}/cancel", headers=holder)
    claimed = client.post("/client/waitlist/claim", json={"session_id": session_id}, headers=asker)

    assert claimed.status_code == 201, claimed.text
    assert client.get("/client/waitlist", headers=asker).json() == []  # the request is done
    roster = client.get(f"/sessions/{session_id}/bookings", headers=studio["headers"]).json()
    assert [b["status"] for b in roster if b["status"] != "cancelled"] == ["booked"]


def test_a_freed_appointment_is_offered_and_rebooked(
    client: TestClient,
    barber: dict,  # noqa: F811
    auth: AuthHeaders,
) -> None:
    day, haircut = barber["day"], barber["haircut"]
    holder_user, asker_user = uuid4(), uuid4()
    code = join_code(client, barber)
    join(client, auth, holder_user, code)
    join(client, auth, asker_user, code)
    holder = auth(holder_user, barber["tenant_id"])
    asker = auth(asker_user, barber["tenant_id"])
    booked = client.post(
        "/client/appointments",
        json={"service_id": haircut["id"], "staff_user_id": str(barber["owner"]),
              "starts_at": at(day, "10:00")},
        headers=holder,
    ).json()  # fmt: skip
    wait = client.post(
        "/client/waitlist",
        json={"service_id": haircut["id"], "kind": "range", "day": day.isoformat(),
              "from_time": "09:00", "to_time": "11:00"},
        headers=asker,
    )  # fmt: skip
    assert wait.status_code == 201, wait.text

    client.post(f"/client/bookings/{booked['my_booking']['id']}/cancel", headers=holder)

    [entry] = client.get("/client/waitlist", headers=asker).json()
    assert entry["offer_session_id"] is not None
    assert kinds(client, asker) == ["waitlist_spot_open"]
    claimed = client.post(
        "/client/waitlist/claim", json={"session_id": entry["offer_session_id"]}, headers=asker
    )
    assert claimed.status_code == 201, claimed.text
    listed = client.get(
        "/sessions", params={"start": day.isoformat(), "days": 1}, headers=barber["headers"]
    ).json()
    assert len(listed) == 1 and listed[0]["appointment_client"] is not None
    assert client.get("/client/waitlist", headers=asker).json() == []
    # The time is held again, so a second claim of the same offer finds it gone.
    again = client.post(
        "/client/waitlist/claim", json={"session_id": entry["offer_session_id"]}, headers=asker
    )
    assert again.status_code == 409


def test_request_rules(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    asker = app_clients(client, auth, studio, 1)[0]["headers"]
    service = studio["service"]["id"]
    today = local_today()

    def ask(**body: object):
        body = {
            "service_id": service,
            "kind": "day",
            "day": (today + timedelta(days=3)).isoformat(),
            **body,
        }
        return client.post("/client/waitlist", json=body, headers=asker)

    assert ask(kind="range").status_code == 422  # a range needs its hours
    assert ask(kind="range", from_time="12:00", to_time="10:00").status_code == 422
    assert ask(kind="slot").status_code == 422  # a slot needs its start
    assert ask(day=(today - timedelta(days=1)).isoformat()).status_code == 422
    assert ask(service_id=str(uuid4())).status_code == 404
    first = ask()
    assert first.status_code == 201
    assert ask().status_code == 409 and ask().json()["detail"] == "already_waiting"
    for offset in range(4, 8):
        assert ask(day=(today + timedelta(days=offset)).isoformat()).status_code == 201
    over = ask(day=(today + timedelta(days=9)).isoformat())
    assert over.status_code == 409 and over.json()["detail"] == "too_many_requests"
    assert len(client.get("/client/waitlist", headers=asker).json()) == 5

    left = client.delete(f"/client/waitlist/{first.json()['id']}", headers=asker)
    assert left.status_code == 204
    assert client.delete(f"/client/waitlist/{first.json()['id']}", headers=asker).status_code == 404
    assert len(client.get("/client/waitlist", headers=asker).json()) == 4


def test_off_means_no_waitlist(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    set_waitlist(client, studio["headers"], waitlist_enabled=False)
    session_id = new_session(client, studio, capacity=1)
    first, second = app_clients(client, auth, studio, 2)
    assert (
        client.post(f"/client/sessions/{session_id}/bookings", headers=first["headers"]).status_code
        == 201
    )

    full = client.post(f"/client/sessions/{session_id}/bookings", headers=second["headers"])
    ask = client.post(
        "/client/waitlist",
        json={"service_id": studio["service"]["id"], "kind": "day",
              "day": (local_today() + timedelta(days=20)).isoformat()},
        headers=second["headers"],
    )  # fmt: skip

    assert full.status_code == 409 and full.json()["detail"] == "session_full"
    assert ask.status_code == 409 and ask.json()["detail"] == "waitlist_off"
    # Staff can still fill the class beyond its capacity: that is a different path.
    assert (
        client.get("/client/businesses", headers=second["headers"]).json()[0]["waitlist_class"]
        == "off"
    )


def test_one_service_can_work_differently(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    service = studio["service"]["id"]
    set_waitlist(client, studio["headers"], waitlist_class_mode="manual")
    patched = client.patch(
        f"/services/{service}", json={"waitlist_mode": "first_come"}, headers=studio["headers"]
    )
    assert patched.status_code == 200 and patched.json()["waitlist_mode"] == "first_come"
    _, people, bookings = full_class(client, auth, studio, names=2)
    client.post(f"/client/bookings/{bookings[0]['id']}/cancel", headers=people[0]["headers"])
    assert "waitlist_spot_open" in kinds(client, people[1]["headers"])  # the service's own mode
    cleared = client.patch(
        f"/services/{service}", json={"waitlist_mode": None}, headers=studio["headers"]
    )
    assert cleared.json()["waitlist_mode"] is None


def test_the_team_screen_summary_and_removal(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, _people, _bookings = full_class(client, auth, studio, names=2)
    asker = app_clients(client, auth, studio, 1)[0]["headers"]
    day = (local_today() + timedelta(days=20)).isoformat()
    request = client.post(
        "/client/waitlist",
        json={"service_id": studio["service"]["id"], "kind": "day", "day": day},
        headers=asker,
    ).json()

    entries = client.get("/waitlist", params={"day": day}, headers=studio["headers"]).json()
    assert sorted(e["source"] for e in entries) == ["booking", "request"]
    none = client.get(
        "/waitlist", params={"day": (local_today() + timedelta(days=2)).isoformat()},
        headers=studio["headers"],
    ).json()  # fmt: skip
    assert none == []
    summary = client.get("/waitlist/summary", headers=studio["headers"]).json()
    assert summary["waiting"] == 2 and summary["services"][0]["waiting"] == 2

    removed = client.delete(f"/waitlist/requests/{request['id']}", headers=studio["headers"])
    assert removed.status_code == 204
    assert client.get("/client/waitlist", headers=asker).json() == []
    nothing = client.post(
        f"/waitlist/requests/{request['id']}/admit", json={}, headers=studio["headers"]
    )
    assert nothing.status_code == 404


def test_other_businesses_and_clients_see_nothing(
    client: TestClient,
    studio: dict,
    auth: AuthHeaders,
    barber: dict,  # noqa: F811
) -> None:
    asker = app_clients(client, auth, studio, 1)[0]
    day = (local_today() + timedelta(days=5)).isoformat()
    request = client.post(
        "/client/waitlist",
        json={"service_id": studio["service"]["id"], "kind": "day", "day": day},
        headers=asker["headers"],
    ).json()
    other = app_clients(client, auth, studio, 1)[0]["headers"]

    assert client.get("/client/waitlist", headers=other).json() == []
    assert client.delete(f"/client/waitlist/{request['id']}", headers=other).status_code == 404
    assert client.get("/waitlist", headers=barber["headers"]).json() == []
    assert (
        client.delete(f"/waitlist/requests/{request['id']}", headers=barber["headers"]).status_code
        == 404
    )
    assert (
        client.post(
            "/client/waitlist/claim", json={"session_id": str(uuid4())}, headers=other
        ).status_code
        == 404
    )


def test_a_freed_court_is_offered_and_paid_for_when_taken(
    client: TestClient,
    club: dict,  # noqa: F811
    auth: AuthHeaders,
) -> None:
    holder, asker = club_member(client, club, auth), club_member(client, club, auth)
    when = at(club["day"], "18:00")
    court = club["courts"][0]["id"]
    body = {"service_id": club["padel"]["id"], "room_id": court, "starts_at": when, "minutes": 60}
    held = client.post(
        "/client/resources/reservations",
        json={**body, "pay": True, "idempotency_key": "court-hold-0001"},
        headers=holder,
    )
    assert held.status_code == 201, held.text
    # Exactly this time on any court, for anyone who cannot book it.
    request = client.post(
        "/client/waitlist",
        json={"service_id": club["padel"]["id"], "kind": "slot", "starts_at": when},
        headers=asker,
    )
    assert request.status_code == 201, request.text

    client.post(
        f"/client/bookings/{held.json()['session']['my_booking']['id']}/cancel", headers=holder
    )
    [entry] = client.get("/client/waitlist", headers=asker).json()
    assert entry["offer_session_id"] is not None  # the reserved session was released, yet offered

    unpaid = client.post(
        "/client/waitlist/claim", json={"session_id": entry["offer_session_id"]}, headers=asker
    )
    paid = client.post(
        "/client/waitlist/claim",
        json={
            "session_id": entry["offer_session_id"],
            "pay": True,
            "idempotency_key": "claim-0001",
        },
        headers=asker,
    )

    assert unpaid.status_code == 402 and unpaid.json()["detail"] == "payment_required"
    assert paid.status_code == 201, paid.text
    assert client.get("/client/waitlist", headers=asker).json() == []
    mine = client.get("/client/bookings", headers=asker).json()
    assert [b["status"] for b in mine] == ["booked"]
