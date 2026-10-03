from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import book, new_client, new_session, set_status


def card(client: TestClient, headers: dict, credits: int = 2, validity_days: int = 60) -> dict:
    created = client.post(
        "/plans",
        json={
            "name": f"{credits}-class card",
            "kind": "punch_card",
            "price_amount": 12000,
            "validity_days": validity_days,
            "credits": credits,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


def sell(client: TestClient, headers: dict, client_id: str, plan_id: str, **extra) -> dict:
    body = {"plan_id": plan_id, "idempotency_key": f"sale-{uuid4()}", **extra}
    sold = client.post(f"/clients/{client_id}/entitlements", json=body, headers=headers)
    assert sold.status_code == 201, sold.text
    return sold.json()


def test_new_business_gets_pack_default_plans(client: TestClient, studio: dict) -> None:
    plans = client.get("/plans", headers=studio["headers"]).json()

    assert [(p["kind"], p["credits"], p["price_currency"]) for p in plans] == [
        ("membership", None, "ILS"),
        ("punch_card", 10, "ILS"),
        ("punch_card", 1, "ILS"),
    ]
    assert plans[0]["name"] == "מנוי חודשי ללא הגבלה"  # the business's language (he)
    tenant = client.get("/tenants/current", headers=studio["headers"]).json()
    assert tenant["booking_requires_plan"] is True


def test_plan_validation_and_update(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    bad = client.post(
        "/plans",
        json={
            "name": "X",
            "kind": "membership",
            "price_amount": 1,
            "validity_days": 30,
            "credits": 5,
        },
        headers=headers,
    )
    assert bad.status_code == 422

    plan = card(client, headers)
    updated = client.patch(
        f"/plans/{plan['id']}", json={"price_amount": 9900, "active": False}, headers=headers
    ).json()
    assert (updated["price_amount"], updated["active"], updated["credits"]) == (9900, False, 2)


def test_sale_is_idempotent_and_records_a_simulated_payment(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    plan = card(client, headers, credits=5, validity_days=30)
    body = {"plan_id": plan["id"], "idempotency_key": "front-desk-0001", "starts_on": "2026-11-01"}

    first = client.post(f"/clients/{dana}/entitlements", json=body, headers=headers).json()
    retry = client.post(f"/clients/{dana}/entitlements", json=body, headers=headers).json()

    assert first["id"] == retry["id"]
    assert (first["starts_on"], first["ends_on"]) == ("2026-11-01", "2026-11-30")
    assert first["credits_remaining"] == 5 and first["state"] == "upcoming"
    with engine.connect() as connection:
        payments = connection.execute(
            text("SELECT amount, currency, provider, status FROM app.payments")
        ).all()
    assert payments == [(12000, "ILS", "simulated", "succeeded")]


def test_punch_card_credits_are_used_and_returned(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    entitlement = sell(client, headers, dana, card(client, headers, credits=2)["id"])
    first, second, third = (
        new_session(client, studio, on=date.today() + timedelta(days=d)) for d in (3, 4, 5)
    )

    b1 = book(client, headers, first, dana).json()
    book(client, headers, second, dana)
    walk_in = book(client, headers, third, dana).json()  # staff may book without credits

    assert b1["plan_name"] == "2-class card"
    assert walk_in["plan_name"] is None
    [state] = client.get(f"/clients/{dana}/entitlements", headers=headers).json()
    assert (state["credits_used"], state["credits_remaining"], state["state"]) == (2, 0, "used_up")

    set_status(client, headers, b1["id"], "cancelled")  # in time: the credit comes back
    [state] = client.get(f"/clients/{dana}/entitlements", headers=headers).json()
    assert state["id"] == entitlement["id"]
    assert state["credits_remaining"] == 1


def test_memberships_are_used_before_cards(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    plans = client.get("/plans", headers=headers).json()
    sell(client, headers, dana, plans[1]["id"])  # 10-class card
    sell(client, headers, dana, plans[0]["id"])  # monthly unlimited

    booking = book(
        client, headers, new_session(client, studio, on=date.today() + timedelta(days=2)), dana
    ).json()

    assert booking["plan_name"] == plans[0]["name"]


def test_freeze_blocks_its_days_and_extends_the_end(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    today = date.today()
    entitlement = sell(
        client, headers, dana, card(client, headers, credits=5, validity_days=30)["id"]
    )
    frozen_from, frozen_to = today + timedelta(days=5), today + timedelta(days=9)

    frozen = client.post(
        f"/entitlements/{entitlement['id']}/freezes",
        json={"starts_on": frozen_from.isoformat(), "ends_on": frozen_to.isoformat()},
        headers=headers,
    )

    assert frozen.status_code == 201
    assert frozen.json()["ends_on"] == (today + timedelta(days=29 + 5)).isoformat()
    during = book(client, headers, new_session(client, studio, on=frozen_from), dana).json()
    after = book(
        client, headers, new_session(client, studio, on=frozen_to + timedelta(days=1)), dana
    ).json()
    assert during["plan_name"] is None
    assert after["plan_name"] == "5-class card"
    overlap = client.post(
        f"/entitlements/{entitlement['id']}/freezes",
        json={"starts_on": frozen_to.isoformat(), "ends_on": frozen_to.isoformat()},
        headers=headers,
    )
    assert overlap.status_code == 409


def test_cancelled_entitlement_is_not_used(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    entitlement = sell(client, headers, dana, card(client, headers)["id"])

    cancelled = client.post(f"/entitlements/{entitlement['id']}/cancel", headers=headers).json()

    assert cancelled["state"] == "cancelled"
    booking = book(client, headers, new_session(client, studio), dana).json()
    assert booking["plan_name"] is None


def test_staff_cannot_sell(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    dana = new_client(client, studio["headers"], "Dana")
    plan = client.get("/plans", headers=studio["headers"]).json()[0]
    coach = auth(studio["coach"], studio["tenant_id"])
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")

    body = {"plan_id": plan["id"], "idempotency_key": "coach-sale-1"}
    assert client.post(f"/clients/{dana}/entitlements", json=body, headers=coach).status_code == 403
    desk_sale = client.post(
        f"/clients/{dana}/entitlements",
        json={**body, "idempotency_key": "desk-sale-1"},
        headers=auth(desk, studio["tenant_id"]),
    )
    assert desk_sale.status_code == 201
    assert client.post("/plans", json={}, headers=coach).status_code == 403
