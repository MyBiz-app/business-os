from datetime import timedelta

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_checkouts import setup


def start(client: TestClient, headers: dict, plan_id: str) -> dict:
    return client.post("/client/checkouts", json={"plan_id": plan_id}, headers=headers).json()


def test_percent_code_discounts_and_counts_a_use(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _joined, headers, card = setup(client, auth, studio)
    created = client.post(
        "/promo-codes",
        json={"code": "welcome20", "percent_off": 20, "max_uses": 1},
        headers=studio["headers"],
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "WELCOME20"

    checkout = start(client, headers, card["id"])
    bad = client.post(
        f"/client/checkouts/{checkout['id']}/promo", json={"code": "NOPE"}, headers=headers
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_code"
    applied = client.post(
        f"/client/checkouts/{checkout['id']}/promo", json={"code": " welcome20 "}, headers=headers
    ).json()
    expected = card["price_amount"] - round(card["price_amount"] * 0.2)
    assert applied["amount"] == expected and applied["promo_code"] == "WELCOME20"
    assert applied["list_amount"] == card["price_amount"]

    paid = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)
    assert paid.json()["entitlement"]["price_amount"] == expected
    [code] = client.get("/promo-codes", headers=studio["headers"]).json()
    assert code["uses"] == 1 and code["discount_given"] == card["price_amount"] - expected

    # Used up: max_uses 1.
    second = start(client, headers, card["id"])
    used_up = client.post(
        f"/client/checkouts/{second['id']}/promo", json={"code": "WELCOME20"}, headers=headers
    )
    assert used_up.status_code == 422
    assert client.delete(f"/promo-codes/{code['id']}", headers=studio["headers"]).status_code == 409


def test_amount_code_for_one_plan_within_dates(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _joined, headers, card = setup(client, auth, studio)
    plans = client.get("/plans", headers=studio["headers"]).json()
    other = next(p for p in plans if p["id"] != card["id"])
    tomorrow = (local_today() + timedelta(days=1)).isoformat()
    client.post(
        "/promo-codes",
        json={"code": "CARD50", "amount_off": 5000, "plan_id": card["id"]},
        headers=studio["headers"],
    )
    client.post(
        "/promo-codes",
        json={"code": "LATER", "percent_off": 10, "starts_on": tomorrow},
        headers=studio["headers"],
    )

    on_card = start(client, headers, card["id"])
    applied = client.post(
        f"/client/checkouts/{on_card['id']}/promo", json={"code": "CARD50"}, headers=headers
    ).json()
    assert applied["discount"] == 5000
    removed = client.post(
        f"/client/checkouts/{on_card['id']}/promo", json={"code": None}, headers=headers
    ).json()
    assert removed["amount"] == card["price_amount"] and removed["promo_code"] is None

    on_other = start(client, headers, other["id"])
    for code in ("CARD50", "LATER"):
        response = client.post(
            f"/client/checkouts/{on_other['id']}/promo", json={"code": code}, headers=headers
        )
        assert response.status_code == 422, code


def test_paused_codes_and_strangers(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    _joined, headers, card = setup(client, auth, studio)
    code = client.post(
        "/promo-codes", json={"code": "PAUSE", "percent_off": 50}, headers=studio["headers"]
    ).json()
    client.patch(f"/promo-codes/{code['id']}", json={"active": False}, headers=studio["headers"])
    checkout = start(client, headers, card["id"])
    paused = client.post(
        f"/client/checkouts/{checkout['id']}/promo", json={"code": "PAUSE"}, headers=headers
    )
    assert paused.status_code == 422
    _other_member, stranger, _card = setup(client, auth, studio)
    response = client.post(
        f"/client/checkouts/{checkout['id']}/promo", json={"code": "PAUSE"}, headers=stranger
    )
    assert response.status_code == 404
    both = client.post(
        "/promo-codes",
        json={"code": "BOTH", "percent_off": 5, "amount_off": 100},
        headers=studio["headers"],
    )
    assert both.status_code == 422
    dup = client.post(
        "/promo-codes", json={"code": "pause", "percent_off": 5}, headers=studio["headers"]
    )
    assert dup.status_code == 409
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/promo-codes", headers=coach).status_code == 200
    assert (
        client.post(
            "/promo-codes", json={"code": "X1X", "percent_off": 5}, headers=coach
        ).status_code
        == 403
    )
