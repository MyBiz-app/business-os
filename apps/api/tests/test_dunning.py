"""VAT on MyBiz invoices, consecutive numbers, dunning and cancellation (go-live GL20)."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.commerce.billing import bill_businesses, vat_of
from app.commerce.dunning import run_dunning
from app.messaging.email import Email
from tests.conftest import AuthHeaders, add_member, make_staff
from tests.test_billing import end_trial, run_billing


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


def age_invoices(engine: Engine, tenant_id: object, days: int) -> None:
    """Makes the business's open invoices `days` days old."""
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.platform_invoices SET issued_at = now() - make_interval(days => :d)
                WHERE tenant_id = :t AND status = 'open'
            """),
            {"d": days, "t": tenant_id},
        )


def dunn(engine: Engine, outbox: Outbox, at: datetime | None = None) -> dict[str, int]:
    with engine.begin() as connection:
        return run_dunning(connection, at or datetime.now(UTC), outbox)


def one_overdue_business(client: TestClient, studio: dict, engine: Engine) -> None:
    client.put(
        "/tenants/current/modules", json={"modules": {"client_app": 1}}, headers=studio["headers"]
    )
    end_trial(engine, studio["tenant_id"], days_ago=40)
    assert run_billing(engine) == 1


def test_vat_rounds_half_up() -> None:
    assert vat_of(14800, 1800) == 2664
    assert vat_of(5, 1800) == 1  # 0.9 rounds up
    assert vat_of(2, 1800) == 0  # 0.36 rounds down
    assert vat_of(10000, 0) == 0


def test_a_currency_without_a_rate_is_billed_without_vat(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET currency = 'USD' WHERE id = :t"),
            {"t": studio["tenant_id"]},
        )
    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    [invoice] = client.get("/billing", headers=studio["headers"]).json()["invoices"]
    assert invoice["vat_rate_bp"] == 0 and invoice["vat_amount"] == 0
    assert invoice["total"] == invoice["subtotal"]


def test_the_rate_in_force_on_the_issue_day_is_used(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO app.vat_rates VALUES ('ILS', '2020-01-01', 1700)"))
        connection.execute(text("DELETE FROM app.vat_rates WHERE valid_from = '2025-01-01'"))
    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    [invoice] = client.get("/billing", headers=studio["headers"]).json()["invoices"]
    assert invoice["vat_rate_bp"] == 1700


def test_invoice_numbers_have_no_gaps_even_after_a_rollback(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    end_trial(engine, studio["tenant_id"], days_ago=65)
    try:
        with engine.begin() as connection:
            bill_businesses(connection, datetime.now(UTC))
            raise RuntimeError("the run fails after writing")
    except RuntimeError:
        pass
    assert run_billing(engine) == 2
    numbers = sorted(
        i["number"] for i in client.get("/billing", headers=studio["headers"]).json()["invoices"]
    )
    assert numbers[1] == numbers[0] + 1
    assert numbers[0] == 10001  # the rolled back run gave its numbers back


def test_the_invoice_pdf_shows_vat(client: TestClient, studio: dict, engine: Engine) -> None:
    one_overdue_business(client, studio, engine)
    [invoice] = client.get("/billing", headers=studio["headers"]).json()["invoices"]
    pdf = client.get(
        f"/documents/render/platform_invoice/{invoice['id']}.pdf", headers=studio["headers"]
    )
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_reminders_go_out_once_per_day_reached(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    one_overdue_business(client, studio, engine)
    outbox = Outbox()
    age_invoices(engine, studio["tenant_id"], 0)
    assert dunn(engine, outbox)["reminders"] == 1 and len(outbox.sent) == 1
    assert "10001" in outbox.sent[0].text and "174.64" in outbox.sent[0].text
    dunn(engine, outbox)
    assert len(outbox.sent) == 1  # the same day again sends nothing
    age_invoices(engine, studio["tenant_id"], 8)
    dunn(engine, outbox)
    dunn(engine, outbox)
    assert len(outbox.sent) == 2  # days 3 and 7 were passed: one email, not two
    billing = client.get("/billing", headers=studio["headers"]).json()["collection"]
    assert billing["state"] == "active" and billing["read_only_on"] is not None


def test_read_only_after_14_days_then_suspended_after_30(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    one_overdue_business(client, studio, engine)
    outbox = Outbox()

    age_invoices(engine, studio["tenant_id"], 14)
    assert dunn(engine, outbox)["read_only"] == 1
    assert client.get("/services", headers=headers).status_code == 200  # still readable
    blocked = client.post("/clients", json={"first_name": "Dana"}, headers=headers)
    assert blocked.status_code == 403 and blocked.json()["detail"] == "billing_read_only"
    assert client.get("/billing", headers=headers).json()["collection"]["state"] == "read_only"
    assert len(outbox.sent) == 1 and "10001" in outbox.sent[0].text  # one mail for the change

    age_invoices(engine, studio["tenant_id"], 30)
    assert dunn(engine, outbox)["suspended"] == 1
    gone = client.get("/services", headers=headers)
    assert gone.status_code == 403 and gone.json()["detail"] == "billing_suspended"
    # The billing page keeps working so the owner can pay.
    assert client.get("/billing", headers=headers).status_code == 200
    client.post("/billing/payment-method", json={"brand": "visa"}, headers=headers)
    [invoice] = client.get("/billing", headers=headers).json()["invoices"]
    paid = client.post(f"/billing/invoices/{invoice['id']}/pay", headers=headers)
    assert paid.status_code == 200
    assert client.get("/services", headers=headers).status_code == 200
    assert client.post("/clients", json={"first_name": "Dana"}, headers=headers).status_code == 201


def test_a_suspended_business_is_closed_to_its_clients(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    person = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'c@example.com')"), {"id": person}
        )
        connection.execute(
            text("INSERT INTO app.clients (tenant_id, first_name, user_id) VALUES (:t, 'D', :u)"),
            {"t": studio["tenant_id"], "u": person},
        )
        connection.execute(
            text("UPDATE app.tenants SET billing_state = 'read_only' WHERE id = :t"),
            {"t": studio["tenant_id"]},
        )
    headers = auth(person, studio["tenant_id"])
    assert client.get("/client/bookings", headers=headers).status_code == 200  # read-only: fine
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.tenants SET billing_state = 'suspended'"))
    suspended = client.get("/client/bookings", headers=headers)
    assert suspended.status_code == 403 and suspended.json()["detail"] == "billing_suspended"


def test_dunning_can_be_switched_off(client: TestClient, studio: dict, engine: Engine) -> None:
    one_overdue_business(client, studio, engine)
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.dunning_settings SET enabled = false"))
    age_invoices(engine, studio["tenant_id"], 45)
    outbox = Outbox()
    assert dunn(engine, outbox) == {"reminders": 0, "read_only": 0, "suspended": 0, "restored": 0}
    assert outbox.sent == []
    assert (
        client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"]).status_code
        == 201
    )


def test_the_console_sets_the_days_and_extends_grace(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    one_overdue_business(client, studio, engine)
    age_invoices(engine, studio["tenant_id"], 16)
    dunn(engine, Outbox())
    admin = uuid4()
    client.get("/me", headers=auth(admin))
    assert client.get("/platform/billing/overdue", headers=auth(admin)).status_code == 403
    make_staff(engine, admin)

    [row] = client.get("/platform/billing/overdue", headers=auth(admin)).json()
    assert row["tenant_id"] == str(studio["tenant_id"]) and row["billing_state"] == "read_only"

    settings = {
        "enabled": True,
        "reminder_days": [0, 5],
        "read_only_after_days": 20,
        "suspend_after_days": 40,
    }
    assert (
        client.put("/platform/billing/dunning", json=settings, headers=auth(admin)).status_code
        == 200
    )
    assert client.get("/platform/billing/dunning", headers=auth(admin)).json() == settings
    bad = client.put(
        "/platform/billing/dunning",
        json={**settings, "suspend_after_days": 20},
        headers=auth(admin),
    )
    assert bad.status_code == 422

    # A grace extension lifts read-only at once and survives the next run.
    path = f"/platform/businesses/{studio['tenant_id']}/billing/grace"
    assert client.post(path, json={"days": 7}, headers=auth(admin)).status_code == 200
    assert (
        client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"]).status_code
        == 201
    )
    age_invoices(engine, studio["tenant_id"], 45)
    dunn(engine, Outbox())
    assert (
        client.get("/billing", headers=studio["headers"]).json()["collection"]["state"] == "active"
    )
    # ...until it ends.
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET billing_grace_until = now() - interval '1 day'")
        )
    dunn(engine, Outbox())
    assert (
        client.get("/billing", headers=studio["headers"]).json()["collection"]["state"]
        == "suspended"
    )


def test_cancelling_keeps_the_business_until_the_period_ends(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    cancelled = client.post("/billing/cancel", headers=headers)
    assert cancelled.status_code == 200
    # Still in the trial: it ends with the trial, and the business works until then.
    assert cancelled.json()["cancel_at"] is not None and cancelled.json()["state"] == "active"
    assert client.get("/services", headers=headers).status_code == 200

    # Once the end passes the business is suspended (and not billed), but kept.
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.tenants SET cancel_at = now() - interval '1 day',
                    trial_ends_at = now() - interval '45 days'
                WHERE id = :t
            """),
            {"t": studio["tenant_id"]},
        )
    assert client.get("/services", headers=headers).status_code == 403
    assert run_billing(engine) == 1  # the period that ran until the cancellation
    assert run_billing(engine) == 0

    resumed = client.delete("/billing/cancel", headers=headers)
    assert resumed.status_code == 200 and resumed.json()["cancel_at"] is None
    assert client.get("/services", headers=headers).status_code == 200


def test_only_the_owner_cancels(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    assert (
        client.post("/billing/cancel", headers=auth(manager, studio["tenant_id"])).status_code
        == 403
    )
