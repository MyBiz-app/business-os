from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders
from tests.test_bookings import new_client
from tests.test_checkouts import setup


def sell(client: TestClient, studio: dict, client_id: str, method: str = "card") -> dict:
    plans = client.get("/plans", headers=studio["headers"]).json()
    membership = next(p for p in plans if p["kind"] == "membership")
    sold = client.post(
        f"/clients/{client_id}/entitlements",
        json={"plan_id": membership["id"], "method": method, "idempotency_key": f"sale-{uuid4()}"},
        headers=studio["headers"],
    )
    assert sold.status_code == 201, sold.text
    return sold.json()


def test_each_payment_gets_the_next_receipt_number(client: TestClient, studio: dict) -> None:
    dana = new_client(client, studio["headers"], "Dana")
    first = sell(client, studio, dana, method="cash")
    second = sell(client, studio, dana)

    assert (first["receipt_number"], second["receipt_number"]) == (1001, 1002)
    receipt = client.get(f"/receipts/{first['receipt_id']}", headers=studio["headers"]).json()
    assert receipt["client_name"] == "Dana"
    assert receipt["method"] == "cash" and receipt["simulated"] is True
    assert receipt["description"] == first["name"] and receipt["amount"] == first["price_amount"]
    listed = client.get("/receipts", params={"client_id": dana}, headers=studio["headers"]).json()
    assert [r["number"] for r in listed] == [1002, 1001]


def test_clients_see_only_their_own_receipts(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers, card = setup(client, auth, studio)
    checkout = client.post(
        "/client/checkouts", json={"plan_id": card["id"]}, headers=headers
    ).json()
    paid = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)
    other = sell(client, studio, new_client(client, studio["headers"], "Noa"))

    receipt_id = paid.json()["entitlement"]["receipt_id"]
    assert receipt_id is not None
    mine = client.get("/client/receipts", headers=headers).json()
    assert [r["id"] for r in mine] == [receipt_id]
    assert client.get(f"/client/receipts/{receipt_id}", headers=headers).status_code == 200
    assert client.get(f"/client/receipts/{other['receipt_id']}", headers=headers).status_code == 404


def test_erasing_a_client_removes_their_name_from_receipts(
    client: TestClient, studio: dict
) -> None:
    dana = new_client(client, studio["headers"], "Dana")
    sold = sell(client, studio, dana)

    erased = client.post(
        f"/clients/{dana}/erase", json={"confirm": True}, headers=studio["headers"]
    )

    assert erased.status_code == 200, erased.text
    receipt = client.get(f"/receipts/{sold['receipt_id']}", headers=studio["headers"]).json()
    assert receipt["client_email"] is None and "Dana" not in receipt["client_name"]
