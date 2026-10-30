"""Phone alerts for the business owner: what clients do on their own is queued, then pushed once."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.owner_alerts import alert_owners
from app.messaging.push import LogPushSender
from tests.conftest import AuthHeaders
from tests.test_bookings import book, new_client, new_session
from tests.test_client_app import join, join_code, member
from tests.test_leads import with_crm
from tests.test_payroll_notices import add_token

TOKEN = "ExponentPushToken[owner0000000000]"


def at_hour(hour: int) -> datetime:
    """Now, moved to an hour of the (UTC) day, so a test does not depend on the clock."""
    return datetime.now(UTC).replace(hour=hour, minute=0, second=0, microsecond=0)


def run(engine: Engine, push: LogPushSender, hour: int = 12) -> dict[str, int]:
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        return alert_owners(conn, push, at_hour(hour))


def utc_business(engine: Engine, studio: dict) -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        conn.execute(
            text("UPDATE app.tenants SET time_zone = 'UTC' WHERE id = :t"),
            {"t": studio["tenant_id"]},
        )


def test_the_owner_hears_what_clients_did_in_one_push(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    utc_business(engine, studio)
    add_token(engine, studio["owner"], TOKEN)
    session_id = new_session(client, studio, capacity=1)
    alice, bob = uuid4(), uuid4()
    member(client, auth, studio, alice)
    member(client, auth, studio, bob)
    alice_headers = auth(alice, studio["tenant_id"])
    bob_headers = auth(bob, studio["tenant_id"])
    booked = client.post(f"/client/sessions/{session_id}/bookings", headers=alice_headers)
    client.post(f"/client/sessions/{session_id}/bookings", headers=bob_headers)  # waitlisted
    client.post(
        f"/client/bookings/{booked.json()['my_booking']['id']}/cancel", headers=alice_headers
    )
    # The team booking someone itself is not news to the owner.
    walk_in = new_client(client, studio["headers"], "Walk-in")
    book(client, studio["headers"], session_id, walk_in)

    push = LogPushSender()
    result = run(engine, push)
    assert result["businesses"] == 1 and result["pushed"] == 1
    [(tokens, _title, body)] = push.sent
    assert tokens == [TOKEN]
    # Two clients joined; Alice booked once and cancelled once; Bob joined the waitlist.
    assert "New bookings: 1" in body and "Cancellations: 1" in body
    assert "Joined a waitlist: 1" in body and "New clients: 2" in body

    assert run(engine, push)["pushed"] == 0  # told once, however often the job runs
    assert len(push.sent) == 1


def test_an_enquiry_from_the_public_form_is_a_new_enquiry(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    utc_business(engine, studio)
    add_token(engine, studio["owner"], TOKEN)
    with_crm(client, studio)
    code = join_code(client, studio)
    sent = client.post(
        f"/public/businesses/{code}/inquiries",
        json={"first_name": "Noa", "email": "noa@example.com"},
    )
    assert sent.status_code == 202
    push = LogPushSender()
    assert run(engine, push)["pushed"] == 1
    assert "New enquiries: 1" in push.sent[0][2]


def test_quiet_hours_hold_the_push_until_morning(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    utc_business(engine, studio)
    add_token(engine, studio["owner"], TOKEN)
    join(client, auth, uuid4(), join_code(client, studio))
    push = LogPushSender()
    assert run(engine, push, hour=23) == {"queued": 1, "businesses": 0, "pushed": 0}
    assert run(engine, push, hour=3)["pushed"] == 0
    assert run(engine, push, hour=8)["pushed"] == 1  # the morning run sends what waited
    assert "New clients: 1" in push.sent[0][2]


def test_a_switched_off_kind_is_not_sent_and_only_owners_choose(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    utc_business(engine, studio)
    add_token(engine, studio["owner"], TOKEN)
    listed = client.get("/owner-alerts", headers=studio["headers"])
    assert listed.status_code == 200
    assert all(item["enabled"] for item in listed.json()["kinds"])  # on until chosen otherwise
    off = client.put(
        "/owner-alerts/client_joined", json={"enabled": False}, headers=studio["headers"]
    )
    assert off.status_code == 200
    assert {i["kind"]: i["enabled"] for i in off.json()["kinds"]}["client_joined"] is False

    join(client, auth, uuid4(), join_code(client, studio))
    push = LogPushSender()
    assert run(engine, push)["pushed"] == 0  # the only news was a kind the owner turned off

    coach = studio["coach"]  # staff, not an owner
    denied = client.get("/owner-alerts", headers=auth(coach, studio["tenant_id"]))
    assert denied.status_code == 403
    again = client.put(
        "/owner-alerts/lead_new", json={"enabled": False}, headers=auth(coach, studio["tenant_id"])
    )
    assert again.status_code == 403


def test_another_owner_does_not_share_the_choices(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    from tests.conftest import add_member

    second = uuid4()
    add_member(engine, studio["tenant_id"], second, "owner")
    client.put("/owner-alerts/lead_new", json={"enabled": False}, headers=studio["headers"])
    theirs = client.get("/owner-alerts", headers=auth(second, studio["tenant_id"])).json()
    assert all(item["enabled"] for item in theirs["kinds"])
