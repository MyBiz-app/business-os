"""A client's activity timeline: one newest-first feed over bookings, payments, plans, notes,
messages and the history of the lead they came from."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders
from tests.test_bookings import book, new_client, new_session
from tests.test_branch_access import branches, member_at_north  # noqa: F401
from tests.test_leads import with_crm
from tests.test_receipts import sell


def feed(client: TestClient, headers: dict, client_id: str, **params) -> list[dict]:
    response = client.get(f"/clients/{client_id}/activity", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_feed_gathers_every_kind_newest_first(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    dana = client.post(
        "/clients", json={"first_name": "Dana", "email": "dana@example.com"}, headers=headers
    ).json()["id"]
    sold = sell(client, studio, dana)
    book(client, headers, new_session(client, studio), dana)
    note = client.post(f"/clients/{dana}/notes", json={"body": "Knee, go easy"}, headers=headers)
    assert note.status_code == 201, note.text
    lead = client.post(
        "/leads", json={"first_name": "Dana", "email": "dana@example.com"}, headers=headers
    ).json()
    client.post(f"/leads/{lead['id']}/convert", headers=headers)

    events = feed(client, headers, dana)

    kinds = {e["kind"] for e in events}
    assert {"booking", "payment", "plan", "note", "lead"} <= kinds
    times = [e["occurred_at"] for e in events]
    assert times == sorted(times, reverse=True)
    payment = next(e for e in events if e["kind"] == "payment")
    assert payment["amount"] == sold["price_amount"] and payment["status"] == "succeeded"
    assert next(e for e in events if e["kind"] == "note")["detail"] == "Knee, go easy"
    assert len({e["id"] for e in events}) == len(events)


def test_the_feed_is_one_clients_and_paged(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    noa = new_client(client, headers, "Noa")
    sell(client, studio, dana)
    sell(client, studio, noa)

    everything = feed(client, headers, dana)
    first = feed(client, headers, dana, limit=1)
    rest = feed(client, headers, dana, limit=1, offset=1)

    assert len(everything) == 2  # the payment and the plan sold, none of Noa's
    assert [first[0]["id"], rest[0]["id"]] == [e["id"] for e in everything]
    assert (
        client.get(f"/clients/{dana}/activity", params={"limit": 201}, headers=headers).status_code
        == 422
    )


def test_an_unknown_client_is_not_found(client: TestClient, studio: dict) -> None:
    missing = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/clients/{missing}/activity", headers=studio["headers"])
    assert response.status_code == 404


def test_a_branch_member_gets_their_branch_only(
    client: TestClient,
    auth: AuthHeaders,
    engine: Engine,
    studio: dict,
    branches: dict,  # noqa: F811
) -> None:
    mine = member_at_north(client, auth, engine, studio, branches)

    assert (
        client.get(f"/clients/{branches['south_client']}/activity", headers=mine).status_code == 404
    )
    north = feed(client, mine, branches["north_client"])
    assert [e["kind"] for e in north] == ["booking"]
    # A client with no home branch is everyone's, but only the bookings at one's own branch show.
    shared = new_client(client, branches["owner"], "Shared")
    book(client, branches["owner"], branches["south_session"], shared)
    book(client, branches["owner"], branches["north_session"], shared)
    seen = feed(client, mine, shared)
    assert len([e for e in seen if e["kind"] == "booking"]) == 1
