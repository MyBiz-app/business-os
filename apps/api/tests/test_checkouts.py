from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders
from tests.test_client_app import join, join_code


def setup(client: TestClient, auth: AuthHeaders, studio: dict, online: bool = True) -> tuple:
    client.patch("/tenants/current", json={"online_sales": online}, headers=studio["headers"])
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    plans = client.get("/plans", headers=studio["headers"]).json()
    card = next(p for p in plans if p["kind"] == "punch_card")
    return joined, auth(user, studio["tenant_id"]), card


def test_client_buys_a_plan_with_a_simulated_payment(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    joined, headers, card = setup(client, auth, studio)
    assert client.get("/client/businesses", headers=headers).json()[0]["online_sales"] is True

    started = client.post("/client/checkouts", json={"plan_id": card["id"]}, headers=headers)
    assert started.status_code == 201, started.text
    checkout = started.json()
    assert checkout["status"] == "pending" and checkout["simulated"] is True
    assert checkout["amount"] == card["price_amount"]

    paid = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)
    again = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)

    assert paid.status_code == 200, paid.text
    assert paid.json()["checkout"]["status"] == "paid"
    entitlement = paid.json()["entitlement"]
    assert entitlement["name"] == card["name"] and entitlement["state"] == "active"
    assert again.json()["entitlement"]["id"] == entitlement["id"]  # completed once
    mine = client.get("/client/entitlements", headers=headers).json()
    assert [e["id"] for e in mine] == [entitlement["id"]]
    staff_view = client.get(
        f"/clients/{joined['client_id']}/entitlements", headers=studio["headers"]
    ).json()
    assert len(staff_view) == 1
    revenue = client.get(
        "/metrics",
        params={"start": entitlement["starts_on"], "end": entitlement["starts_on"],
                "keys": ["revenue"]},
        headers=studio["headers"],
    ).json()  # fmt: skip
    assert revenue[0]["value"] == card["price_amount"]


def test_online_sales_must_be_on(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    _, headers, card = setup(client, auth, studio, online=False)

    response = client.post("/client/checkouts", json={"plan_id": card["id"]}, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "online_sales_off"


def test_clients_cannot_complete_others_checkouts(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    _, alice, card = setup(client, auth, studio)
    bob_user = uuid4()
    join(client, auth, bob_user, join_code(client, studio))
    bob = auth(bob_user, studio["tenant_id"])
    checkout = client.post("/client/checkouts", json={"plan_id": card["id"]}, headers=alice).json()

    assert client.get(f"/client/checkouts/{checkout['id']}", headers=bob).status_code == 404
    pay = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=bob)
    assert pay.status_code == 404
    with engine.connect() as connection:
        status = connection.execute(text("SELECT status FROM app.checkouts")).scalar_one()
    assert status == "pending"


def test_inactive_plans_cannot_be_bought(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers, card = setup(client, auth, studio)
    client.patch(f"/plans/{card['id']}", json={"active": False}, headers=studio["headers"])

    response = client.post("/client/checkouts", json={"plan_id": card["id"]}, headers=headers)

    assert response.status_code == 404
