from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.billing import add_months, bill_businesses, periods_due
from tests.conftest import STUDIO, AuthHeaders, add_member, make_staff
from tests.test_documents_time import PDF, upload


def test_months_are_clamped_to_shorter_months() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_only_finished_periods_are_due() -> None:
    anchor = date(2026, 1, 10)
    due = periods_due(anchor, None, date(2026, 3, 15))
    assert [(p.start, p.end) for p in due] == [
        (date(2026, 1, 10), date(2026, 2, 9)),
        (date(2026, 2, 10), date(2026, 3, 9)),
    ]
    assert periods_due(anchor, date(2026, 2, 10), date(2026, 3, 15)) == []


def end_trial(engine: Engine, tenant_id: object, days_ago: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.tenants SET trial_ends_at = now() - make_interval(days => :d)
                WHERE id = :t
            """),
            {"d": days_ago, "t": tenant_id},
        )


def run_billing(engine: Engine) -> int:
    with engine.begin() as connection:
        return bill_businesses(connection, datetime.now(UTC))


def test_new_business_is_in_trial(client: TestClient, studio: dict) -> None:
    billing = client.get("/billing", headers=studio["headers"]).json()
    assert billing["in_trial"] is True and billing["trial_days_left"] == 14
    assert billing["invoices"] == [] and billing["payment_method"] is None
    assert billing["estimate"]["total"] > 0


def test_usage_counts_against_the_bundle(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    usage = client.get("/billing", headers=headers).json()["usage"]
    assert usage["pack"] is None and usage["messages"] == 0 and usage["storage_bytes"] == 0
    assert usage["messages_included"] == 200 and usage["storage_included_bytes"] == 2 * 1024**3

    modules = {"whatsapp": 1, "pack_plus": 1}
    client.put("/tenants/current/modules", json={"modules": modules}, headers=headers)
    dana = client.post(
        "/clients", json={"first_name": "Dana", "phone": "050-1111111"}, headers=headers
    ).json()["id"]
    sent = client.post("/messages/direct", json={"client_id": dana, "body": "Hi"}, headers=headers)
    assert sent.status_code == 201, sent.text
    upload(client, headers, dana, "terms.pdf")

    usage = client.get("/billing", headers=headers).json()["usage"]
    assert usage["pack"] == "pack_plus" and usage["messages_included"] == 1000
    assert usage["messages"] == 1 and usage["storage_bytes"] == len(PDF)


def test_invoices_after_the_trial(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"client_app": 1}}, headers=headers)
    end_trial(engine, studio["tenant_id"], days_ago=65)

    assert run_billing(engine) == 2
    assert run_billing(engine) == 0  # one invoice per period

    billing = client.get("/billing", headers=headers).json()
    assert billing["in_trial"] is False
    first, second = billing["invoices"][1], billing["invoices"][0]
    assert first["status"] == "open" and second["number"] == first["number"] + 1
    assert billing["balance_due"] == first["total"] + second["total"]
    invoice = client.get(f"/billing/invoices/{first['id']}", headers=headers).json()
    assert [(line["key"], line["amount"]) for line in invoice["lines"]] == [
        ("core", 9900),
        ("client_app", 4900),
    ]
    assert invoice["total"] == 14800 and invoice["simulated"] is True

    # Paying needs a (test) card.
    unpaid = client.post(f"/billing/invoices/{first['id']}/pay", headers=headers)
    assert unpaid.status_code == 409 and unpaid.json()["detail"] == "no_payment_method"
    card = client.post("/billing/payment-method", json={"brand": "visa"}, headers=headers).json()
    assert card["last4"] == "4242" and card["simulated"] is True
    paid = client.post(f"/billing/invoices/{first['id']}/pay", headers=headers).json()
    assert paid["status"] == "paid" and paid["card_last4"] == "4242"
    again = client.post(f"/billing/invoices/{first['id']}/pay", headers=headers)
    assert again.json()["detail"] == "not_open"


def test_one_time_setup_rides_on_the_first_invoice(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"setup_guided": 1}}, headers=headers)
    end_trial(engine, studio["tenant_id"], days_ago=65)
    run_billing(engine)

    second, first = client.get("/billing", headers=headers).json()["invoices"][:2]
    lines = client.get(f"/billing/invoices/{first['id']}", headers=headers).json()["lines"]
    assert [(line["key"], line["amount"]) for line in lines] == [
        ("core", 9900),
        ("setup_guided", 24900),
    ]
    assert first["total"] == 9900 + 24900 and second["total"] == 9900


def test_card_on_file_is_charged_automatically(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    client.post("/billing/payment-method", json={"brand": "mastercard"}, headers=headers)
    client.put(
        "/billing/details",
        json={
            "billing_name": "Studio Flow Ltd",
            "billing_email": "billing@example.com",
            "tax_id": "514000000",
        },
        headers=headers,
    )
    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)

    [invoice] = client.get("/billing", headers=headers).json()["invoices"]
    assert invoice["status"] == "paid"
    detail = client.get(f"/billing/invoices/{invoice['id']}", headers=headers).json()
    assert detail["billing"]["billing_name"] == "Studio Flow Ltd"
    assert detail["card_last4"] == "4444"


def test_billing_is_for_settings_managers(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/billing", headers=coach).status_code == 403
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    assert client.get("/billing", headers=auth(manager, studio["tenant_id"])).status_code == 200


def test_platform_admins_see_billed_revenue(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    admin = uuid4()
    client.get("/me", headers=auth(admin))
    assert client.get("/platform/billing", headers=auth(admin)).status_code == 403
    make_staff(engine, admin)
    [month] = client.get("/platform/billing", headers=auth(admin)).json()
    due = client.get("/billing", headers=studio["headers"]).json()["balance_due"]
    assert month["currency"] == "ILS" and month["invoices"] == 1 and month["open"] == due > 0
    assert month["month"] <= (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


def test_console_lists_one_business_invoices(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    """The console's business page shows that business's invoices, newest first, and only
    to MyBiz team members who may manage billing."""
    end_trial(engine, studio["tenant_id"], days_ago=65)
    run_billing(engine)
    other = client.post("/tenants", json={**STUDIO, "name": "Other"}, headers=auth(uuid4())).json()
    end_trial(engine, other["id"], days_ago=40)
    run_billing(engine)
    path = f"/platform/businesses/{studio['tenant_id']}/invoices"

    admin = uuid4()
    client.get("/me", headers=auth(admin))
    assert client.get(path, headers=auth(admin)).status_code == 403
    make_staff(engine, admin)
    invoices = client.get(path, headers=auth(admin)).json()

    own = client.get("/billing", headers=studio["headers"]).json()["invoices"]
    assert [i["id"] for i in invoices] == [i["id"] for i in own]  # this business only, same order
    assert len(invoices) == 2 and invoices[0]["number"] > invoices[1]["number"]
    assert all(i["currency"] == "ILS" and i["total"] > 0 for i in invoices)
