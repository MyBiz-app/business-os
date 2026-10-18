import calendar
from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_client_app import member
from tests.test_plans import card, sell

PRICE = 30000


def monthly_plan(client: TestClient, headers: dict, auto_renew: bool = True) -> dict:
    created = client.post(
        "/plans",
        json={
            "name": "Monthly renewing",
            "kind": "membership",
            "price_amount": PRICE,
            "validity_days": 7,  # overridden by the cycle
            "billing_cycle": "monthly",
            "auto_renew": auto_renew,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


def set_rules(client: TestClient, headers: dict, **rules: object) -> dict:
    body = {"allow_requests": True, "min_days": 1, "max_days": 30, **rules}
    saved = client.put("/freeze-rules", json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    return saved.json()


def month_before(day: date) -> date:
    year, month = (day.year, day.month - 1) if day.month > 1 else (day.year - 1, 12)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def renewing_client(
    client: TestClient, auth: AuthHeaders, studio: dict, started_days_ago: int = 0
) -> tuple[dict, dict, dict]:
    """A client of the app holding a renewing monthly membership: (headers, entitlement, joined)."""
    user = uuid4()
    joined = member(client, auth, studio, user)
    entitlement = sell(
        client,
        studio["headers"],
        joined["client_id"],
        monthly_plan(client, studio["headers"])["id"],
        starts_on=(local_today() - timedelta(days=started_days_ago)).isoformat(),
    )
    return auth(user, studio["tenant_id"]), entitlement, joined


def request_freeze(
    client: TestClient, headers: dict, entitlement_id: str, days_from_now: int, days: int, **extra
):
    start = local_today() + timedelta(days=days_from_now)
    body = {
        "starts_on": start.isoformat(),
        "ends_on": (start + timedelta(days=days - 1)).isoformat(),
        "reason": "travel",
        **extra,
    }
    return client.post(
        f"/client/entitlements/{entitlement_id}/freeze-requests", json=body, headers=headers
    )


def test_renewing_plan_sets_cycle_validity_and_next_billing(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    plan = monthly_plan(client, headers)
    assert (plan["billing_cycle"], plan["auto_renew"], plan["validity_days"]) == (
        "monthly",
        True,
        30,
    )

    custom = client.post(
        "/plans",
        json={
            "name": "Ten weeks",
            "kind": "membership",
            "price_amount": 1000,
            "validity_days": 1,
            "billing_cycle": "custom",
            "billing_cycle_days": 70,
        },
        headers=headers,
    )
    assert custom.json()["validity_days"] == 70

    clients = client.post("/clients", json={"first_name": "Dana"}, headers=headers).json()["id"]
    sold = sell(client, headers, clients, plan["id"], starts_on="2026-11-01")
    assert sold["billing_cycle"] == "monthly" and sold["auto_renew"] is True
    assert sold["ends_on"] == "2026-11-30" and sold["next_billing_on"] == "2026-12-01"
    assert sold["next_billing_amount"] == PRICE and sold["freezable"] is True

    prepaid = sell(client, headers, clients, card(client, headers)["id"])
    assert prepaid["next_billing_on"] is None and prepaid["next_billing_amount"] is None


def test_billing_cycle_rules(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    base = {"name": "X", "price_amount": 1, "validity_days": 30}
    for extra in (
        {"kind": "punch_card", "credits": 5, "billing_cycle": "monthly"},
        {"kind": "membership", "auto_renew": True},
        {"kind": "membership", "billing_cycle": "custom"},
        {"kind": "membership", "billing_cycle": "monthly", "billing_cycle_days": 10},
    ):
        response = client.post("/plans", json={**base, **extra}, headers=headers)
        assert response.status_code == 422, extra
    plain = client.post("/plans", json={**base, "kind": "membership"}, headers=headers).json()
    refused = client.patch(f"/plans/{plain['id']}", json={"auto_renew": True}, headers=headers)
    assert refused.status_code == 409


def test_client_request_waits_for_a_manager_who_approves_part_of_it(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    set_rules(client, staff, max_days=30)
    headers, entitlement, joined = renewing_client(client, auth, studio)
    ends_on = date.fromisoformat(entitlement["ends_on"])
    next_billing = date.fromisoformat(entitlement["next_billing_on"])
    start = local_today() + timedelta(days=3)

    preview = client.get(
        f"/client/entitlements/{entitlement['id']}/freeze-preview",
        params={
            "starts_on": start.isoformat(),
            "ends_on": (start + timedelta(days=19)).isoformat(),
        },
        headers=headers,
    ).json()
    assert preview["days"] == 20 and preview["problems"] == []
    assert preview["new_ends_on"] == (ends_on + timedelta(days=20)).isoformat()
    assert preview["billing_mode"] == "defer"
    assert preview["next_billing_to"] == (next_billing + timedelta(days=20)).isoformat()

    sent = request_freeze(client, headers, entitlement["id"], 3, 20, note="Trip abroad")
    assert sent.status_code == 201, sent.text
    request = sent.json()
    assert request["status"] == "pending" and request["days"] == 20

    waiting = client.get("/freeze-requests", params={"status": "pending"}, headers=staff).json()
    assert [r["id"] for r in waiting] == [request["id"]]
    attention = {a["kind"]: a for a in client.get("/attention", headers=staff).json()}
    assert attention["freeze_requests"]["count"] == 1
    assert attention["freeze_requests"]["items"][0]["id"] == joined["client_id"]

    approved = client.post(
        f"/freeze-requests/{request['id']}/approve",
        json={"approved_ends_on": (start + timedelta(days=13)).isoformat(), "note": "14 days"},
        headers=staff,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved" and approved.json()["auto_approved"] is False

    mine = next(
        e for e in client.get("/client/entitlements", headers=headers).json() if e["auto_renew"]
    )
    assert mine["state"] in ("active", "frozen")
    assert mine["ends_on"] == (ends_on + timedelta(days=14)).isoformat()
    assert mine["next_billing_on"] == (next_billing + timedelta(days=14)).isoformat()
    assert mine["freezes"][0]["billing_mode"] == "defer"
    assert mine["next_billing_amount"] == PRICE

    again = client.post(f"/freeze-requests/{request['id']}/approve", json={}, headers=staff)
    assert again.status_code == 409
    inbox = client.get("/client/notifications", headers=headers).json()["items"]
    assert [n["kind"] for n in inbox] == ["freeze_approved"]
    assert client.get("/attention", headers=staff).json() == [] or all(
        a["kind"] != "freeze_requests" for a in client.get("/attention", headers=staff).json()
    )


def test_rejection_tells_the_client_and_changes_nothing(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    set_rules(client, staff)
    headers, entitlement, _ = renewing_client(client, auth, studio)
    request = request_freeze(client, headers, entitlement["id"], 2, 5).json()

    rejected = client.post(
        f"/freeze-requests/{request['id']}/reject", json={"note": "Not now"}, headers=staff
    )

    assert rejected.json()["status"] == "rejected" and rejected.json()["decision_note"] == "Not now"
    mine = next(
        e for e in client.get("/client/entitlements", headers=headers).json() if e["auto_renew"]
    )
    assert mine["freezes"] == [] and mine["ends_on"] == entitlement["ends_on"]
    inbox = client.get("/client/notifications", headers=headers).json()["items"]
    assert inbox[0]["kind"] == "freeze_rejected" and inbox[0]["payload"]["note"] == "Not now"


def test_credit_instead_of_deferring_the_charge(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    set_rules(
        client, staff, billing_mode="credit", fee_amount=1000, auto_approve_reasons=["travel"]
    )
    headers, entitlement, _ = renewing_client(client, auth, studio)
    next_billing = date.fromisoformat(entitlement["next_billing_on"])
    cycle = (next_billing - month_before(next_billing)).days
    credit = -(-PRICE * 20 // cycle)  # rounded up, in the client's favor

    sent = request_freeze(client, headers, entitlement["id"], 1, 20)

    assert sent.json()["status"] == "approved" and sent.json()["auto_approved"] is True
    mine = next(
        e for e in client.get("/client/entitlements", headers=headers).json() if e["auto_renew"]
    )
    assert mine["next_billing_on"] == entitlement["next_billing_on"]  # not moved
    assert mine["freezes"][0]["billing_mode"] == "credit"
    assert (
        mine["freezes"][0]["credit_amount"] == credit and mine["freezes"][0]["fee_amount"] == 1000
    )
    assert mine["next_billing_amount"] == PRICE - credit + 1000


def test_rules_decide_what_may_be_requested(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    headers, entitlement, _ = renewing_client(client, auth, studio)

    off = request_freeze(client, headers, entitlement["id"], 5, 3)
    assert off.status_code == 409 and off.json()["detail"] == "freeze_requests_off"

    set_rules(client, staff, min_days=3, max_days=10, notice_days=5, yearly_bank_days=12)
    for (offset, days), problem in {
        (6, 2): "too_short",
        (6, 11): "too_long",
        (2, 5): "notice_required",
    }.items():
        refused = request_freeze(client, headers, entitlement["id"], offset, days)
        assert refused.status_code == 409 and refused.json()["detail"] == problem

    first = request_freeze(client, headers, entitlement["id"], 6, 8)
    assert first.status_code == 201
    overlap = request_freeze(client, headers, entitlement["id"], 8, 3)
    assert overlap.json()["detail"] == "overlapping_request"
    bank = client.get("/client/freeze-rules", headers=headers).json()["bank"]
    assert bank["used_days"] == 8 and bank["remaining_days"] == 4
    too_much = request_freeze(client, headers, entitlement["id"], 20, 5)
    assert too_much.json()["detail"] == "bank_exceeded"

    withdrawn = client.delete(f"/client/freeze-requests/{first.json()['id']}", headers=headers)
    assert withdrawn.status_code == 204
    assert client.get("/client/freeze-rules", headers=headers).json()["bank"]["used_days"] == 0


def test_coming_back_early_restores_the_dates_and_the_charge(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    headers, entitlement, _ = renewing_client(client, auth, studio, started_days_ago=5)
    today = local_today()
    ends_on = date.fromisoformat(entitlement["ends_on"])
    next_billing = date.fromisoformat(entitlement["next_billing_on"])

    # A freeze that began two days ago and runs 20 days in all (the manager may backdate it).
    frozen = client.post(
        f"/entitlements/{entitlement['id']}/freezes",
        json={
            "starts_on": (today - timedelta(days=2)).isoformat(),
            "ends_on": (today + timedelta(days=17)).isoformat(),
        },
        headers=staff,
    )
    assert frozen.status_code == 201, frozen.text
    freeze = frozen.json()["freezes"][0]
    assert frozen.json()["ends_on"] == (ends_on + timedelta(days=20)).isoformat()

    back = client.post(f"/client/freezes/{freeze['id']}/end-early", headers=headers)
    assert back.status_code == 200, back.text
    assert back.json()["ends_on"] == (ends_on + timedelta(days=2)).isoformat()
    assert back.json()["next_billing_on"] == (next_billing + timedelta(days=2)).isoformat()
    assert back.json()["freezes"][0]["ends_on"] == (today - timedelta(days=1)).isoformat()

    # A freeze that has not begun disappears completely.
    later = client.post(
        f"/entitlements/{entitlement['id']}/freezes",
        json={
            "starts_on": (today + timedelta(days=5)).isoformat(),
            "ends_on": (today + timedelta(days=9)).isoformat(),
        },
        headers=staff,
    ).json()
    undone = client.post(f"/freezes/{later['freezes'][-1]['id']}/end-early", headers=staff).json()
    assert len(undone["freezes"]) == 1
    assert undone["ends_on"] == (ends_on + timedelta(days=2)).isoformat()
    over = client.post(f"/freezes/{freeze['id']}/end-early", headers=staff)
    assert over.status_code == 409


def test_clients_only_reach_their_own_freezes(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    set_rules(client, staff)
    alice, alice_entitlement, _ = renewing_client(client, auth, studio)
    bob, _, _ = renewing_client(client, auth, studio)
    request = request_freeze(client, alice, alice_entitlement["id"], 2, 5).json()

    assert client.get("/client/freeze-requests", headers=bob).json() == []
    assert request_freeze(client, bob, alice_entitlement["id"], 2, 5).status_code == 404
    assert client.delete(f"/client/freeze-requests/{request['id']}", headers=bob).status_code == 404
    assert client.get("/freeze-requests", headers=alice).status_code == 403
    assert (
        client.put("/freeze-rules", json={"allow_requests": False}, headers=alice).status_code
        == 403
    )


def test_a_punch_card_cannot_be_frozen_by_request(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    staff = studio["headers"]
    set_rules(client, staff)
    user = uuid4()
    joined = member(client, auth, studio, user)
    entitlement = sell(client, staff, joined["client_id"], card(client, staff)["id"])

    response = request_freeze(client, auth(user, studio["tenant_id"]), entitlement["id"], 2, 3)

    assert response.status_code == 409 and response.json()["detail"] == "not_freezable"
