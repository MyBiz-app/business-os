"""Quotes, deposits and event projects (#44)."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, local_today
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code


def quote_body(client_id: str, **extra) -> dict:
    return {
        "client_id": client_id,
        "title": "Wedding photography",
        "lines": [
            {"description": "Full day package", "quantity": 1, "unit_price": 800000},
            {"description": "Extra hour", "quantity": 2, "unit_price": 50000},
            {"description": "Album", "quantity": 1, "unit_price": 150000},
        ],
        "deposit_percent": 30,
        "valid_until": (local_today() + timedelta(days=14)).isoformat(),
        "event_date": (local_today() + timedelta(days=60)).isoformat(),
        "event_time": "16:00",
        "event_place": "Garden venue, Herzliya",
        "notes": "Includes editing of 400 photos.",
        **extra,
    }


def new_quote(client: TestClient, headers: dict, client_id: str, **extra) -> dict:
    created = client.post("/quotes", json=quote_body(client_id, **extra), headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


def test_quote_totals_numbers_and_drafts(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    first = new_quote(client, headers, dana)
    second = new_quote(client, headers, dana, title="Engagement shoot")

    assert first["number"] == 1001 and second["number"] == 1002
    assert first["status"] == "draft" and first["total"] == 1_050_000
    assert first["currency"] == "ILS" and len(first["token"]) >= 60
    edited = client.put(
        f"/quotes/{first['id']}",
        json={
            **quote_body(dana),
            "lines": [{"description": "Half day", "quantity": 1, "unit_price": 450000}],
        },
        headers=headers,
    )
    assert edited.status_code == 200 and edited.json()["total"] == 450000
    # A draft isn't visible by its link.
    assert client.get(f"/public/quotes/{first['token']}").status_code == 404

    sent = client.post(f"/quotes/{first['id']}/send", headers=headers)
    assert sent.status_code == 200 and sent.json()["status"] == "sent"
    locked = client.put(f"/quotes/{first['id']}", json=quote_body(dana), headers=headers)
    assert locked.status_code == 409
    copy = client.post(f"/quotes/{first['id']}/copy", headers=headers)
    assert copy.status_code == 201
    assert copy.json()["status"] == "draft" and copy.json()["number"] == 1003
    assert copy.json()["total"] == 450000

    listed = client.get("/quotes", params={"client_id": dana}, headers=headers).json()
    assert [q["number"] for q in listed] == [1003, 1002, 1001]
    assert [
        q["number"]
        for q in client.get("/quotes", params={"status": "sent"}, headers=headers).json()
    ] == [1001]


def test_client_accepts_by_link_and_pays_the_deposit(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    quote = new_quote(client, headers, dana)
    client.post(f"/quotes/{quote['id']}/send", headers=headers)
    link = f"/public/quotes/{quote['token']}"

    seen = client.get(link)
    assert seen.status_code == 200, seen.text
    assert seen.json()["business_name"] == STUDIO["name"]
    assert seen.json()["client_name"] == "Dana" and seen.json()["total"] == 1_050_000
    assert len(seen.json()["lines"]) == 3

    nameless = client.post(f"{link}/answer", json={"accept": True, "name": " "})
    assert nameless.status_code == 422
    accepted = client.post(f"{link}/answer", json={"accept": True, "name": "Dana Levi"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["deposit_due"] == 315_000  # 30%
    again = client.post(f"{link}/answer", json={"accept": False})
    assert again.status_code == 409

    key = f"deposit-{uuid4()}"
    paid = client.post(f"{link}/deposit", json={"idempotency_key": key})
    assert paid.status_code == 201, paid.text
    assert paid.json()["paid"] == 315_000 and paid.json()["deposit_due"] == 0
    twice = client.post(f"{link}/deposit", json={"idempotency_key": key})
    assert twice.status_code == 201 and twice.json()["paid"] == 315_000
    nothing = client.post(f"{link}/deposit", json={"idempotency_key": f"x-{uuid4()}"})
    assert nothing.status_code == 409

    with engine.connect() as connection:
        description = connection.execute(
            text("""
                SELECT r.description FROM app.receipts r JOIN app.payments p ON p.id = r.payment_id
                WHERE p.quote_id = :id
            """),
            {"id": quote["id"]},
        ).scalar_one()
    assert description == "Wedding photography · 1001"

    # Staff record the balance; never more than what is left.
    too_much = client.post(
        f"/quotes/{quote['id']}/payments",
        json={"amount": 800_000, "method": "transfer", "idempotency_key": f"b-{uuid4()}"},
        headers=headers,
    )
    assert too_much.status_code == 422
    balance = client.post(
        f"/quotes/{quote['id']}/payments",
        json={"amount": 735_000, "method": "transfer", "idempotency_key": f"b-{uuid4()}"},
        headers=headers,
    )
    assert balance.status_code == 201 and balance.json()["paid"] == 1_050_000

    events = client.get(
        "/events", params={"start": local_today().isoformat(), "days": 90}, headers=headers
    ).json()
    assert [e["number"] for e in events] == [1001]


def test_declined_and_expired(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    declined = new_quote(client, headers, dana)
    client.post(f"/quotes/{declined['id']}/send", headers=headers)
    answer = client.post(f"/public/quotes/{declined['token']}/answer", json={"accept": False})
    assert answer.json()["status"] == "declined"
    assert (
        client.post(
            f"/public/quotes/{declined['token']}/deposit", json={"idempotency_key": f"k-{uuid4()}"}
        ).status_code
        == 409
    )

    old = new_quote(
        client, headers, dana, valid_until=(local_today() - timedelta(days=1)).isoformat()
    )
    client.post(f"/quotes/{old['id']}/send", headers=headers)
    assert client.get(f"/public/quotes/{old['token']}").json()["status"] == "expired"
    late = client.post(
        f"/public/quotes/{old['token']}/answer", json={"accept": True, "name": "Dana"}
    )
    assert late.status_code == 409 and late.json()["detail"] == "expired"
    assert client.get(f"/quotes/{old['id']}", headers=headers).json()["status"] == "expired"


def test_clients_see_their_sent_quotes_only(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    headers = studio["headers"]
    draft = new_quote(client, headers, joined["client_id"], title="Draft")
    sent = new_quote(client, headers, joined["client_id"], title="Sent")
    client.post(f"/quotes/{sent['id']}/send", headers=headers)
    other = new_quote(client, headers, new_client(client, headers, "Noa"), title="Other")
    client.post(f"/quotes/{other['id']}/send", headers=headers)

    mine = client.get("/client/quotes", headers=auth(user, studio["tenant_id"])).json()
    assert [q["title"] for q in mine] == ["Sent"]
    assert mine[0]["token"] == sent["token"] and draft["id"]
    assert mine[0]["deposit_due"] == 0 and mine[0]["paid"] == 0  # nothing due before accepting
    client.post(f"/public/quotes/{sent['token']}/answer", json={"accept": True, "name": "Dana"})
    accepted = client.get("/client/quotes", headers=auth(user, studio["tenant_id"])).json()[0]
    due = round(accepted["total"] * sent["deposit_percent"] / 100)
    assert accepted["status"] == "accepted" and accepted["deposit_due"] == due


def test_quotes_are_isolated_between_businesses(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    quote = new_quote(client, studio["headers"], new_client(client, studio["headers"], "Dana"))
    owner = uuid4()
    other = client.post("/tenants", json={**STUDIO, "name": "Other"}, headers=auth(owner)).json()
    other_headers = auth(owner, other["id"])
    assert client.get(f"/quotes/{quote['id']}", headers=other_headers).status_code == 404
    assert client.get("/quotes", headers=other_headers).json() == []
    # Numbers are per business.
    mine = new_quote(client, other_headers, new_client(client, other_headers, "Noa"))
    assert mine["number"] == 1001


def test_deposit_through_a_payments_provider(client: TestClient, studio: dict) -> None:
    from tests.test_integrations import connect, signed

    headers = studio["headers"]
    connect(client, headers, "payments", "testpay", terminal="1", secret="k")
    quote = new_quote(client, headers, new_client(client, headers, "Dana"))
    client.post(f"/quotes/{quote['id']}/send", headers=headers)
    link = f"/public/quotes/{quote['token']}"
    client.post(f"{link}/answer", json={"accept": True, "name": "Dana"})

    started = client.post(f"{link}/deposit", json={"idempotency_key": f"d-{uuid4()}"})
    assert started.status_code == 201, started.text
    assert started.json()["pay_url"].startswith("https://pay.example/")
    assert started.json()["paid"] == 0
    checkout_id = started.json()["pay_url"].split("tp-")[1].split("?")[0]

    raw, signature = signed(
        {
            "checkout": checkout_id,
            "ref": "tp-9",
            "status": "succeeded",
            "amount": 315_000,
            "currency": "ILS",
        }
    )
    url = f"/webhooks/payments/testpay/{studio['tenant_id']}"
    done = client.post(url, content=raw, headers={"x-signature": signature})
    assert done.status_code == 204, done.text
    after = client.get(link).json()
    assert after["paid"] == 315_000 and after["deposit_due"] == 0
