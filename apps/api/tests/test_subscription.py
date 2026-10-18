"""Cancelling and pausing the MyBiz subscription: the 14-day refund, the pause fee, the
confirmation email and the console's churn view (round 7, R33)."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.commerce.billing import PAUSE_FEE, bill_businesses
from app.messaging.email import Email
from tests.conftest import AuthHeaders, add_member, make_staff
from tests.test_billing import end_trial, run_billing


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


def pay_first_invoice(client: TestClient, studio: dict, engine: Engine, days_ago: int) -> dict:
    """Ends the trial a month ago, bills once and pays it `days_ago` days back."""
    headers = studio["headers"]
    end_trial(engine, studio["tenant_id"], days_ago=35)
    assert run_billing(engine) == 1
    assert client.post(
        "/billing/payment-method", json={"brand": "visa"}, headers=headers
    ).status_code in (200, 201)
    [invoice] = client.get("/billing", headers=headers).json()["invoices"]
    client.post(f"/billing/invoices/{invoice['id']}/pay", headers=headers)
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.platform_invoices SET paid_at = now() - make_interval(days => :d)
                WHERE id = :id
            """),
            {"d": days_ago, "id": invoice["id"]},
        )
    return invoice


def test_cancelling_records_the_reason_and_refunds_the_first_payment(
    client: TestClient, studio: dict, engine: Engine, monkeypatch
) -> None:
    outbox = Outbox()
    monkeypatch.setattr("app.api.subscription.sender_from_settings", lambda: outbox)
    headers = studio["headers"]
    invoice = pay_first_invoice(client, studio, engine, days_ago=3)

    cancelled = client.post(
        "/billing/cancel", json={"reason": "too_expensive", "note": "  too much "}, headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["cancel_at"] is not None and body["state"] == "active"
    assert body["refund_minor"] == invoice["total"] and body["currency"] == "ILS"
    [mail] = outbox.sent
    assert "/" in mail.details[0][1]  # the date the subscription ends

    with engine.begin() as connection:
        row = connection.execute(
            text("""
                SELECT outcome, reason, note, refund_minor, refund_invoice_id
                FROM app.subscription_cancellations WHERE tenant_id = :t
            """),
            {"t": studio["tenant_id"]},
        ).one()
    assert row.outcome == "cancelled" and row.reason == "too_expensive"
    assert row.note == "too much" and row.refund_minor == invoice["total"]

    # Cancelling twice does not repeat anything.
    again = client.post("/billing/cancel", headers=headers)
    assert again.status_code == 200 and len(outbox.sent) == 1

    # Taking it back marks the row; the same payment is never refunded twice.
    assert client.delete("/billing/cancel", headers=headers).json()["cancel_at"] is None
    second = client.post("/billing/cancel", headers=headers).json()
    assert second["refund_minor"] is None


def test_no_refund_after_14_days_or_in_the_trial(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    trial = client.post("/billing/cancel", headers=headers).json()
    assert trial["refund_minor"] is None
    client.delete("/billing/cancel", headers=headers)

    pay_first_invoice(client, studio, engine, days_ago=15)
    late = client.post("/billing/cancel", json={"reason": "other"}, headers=headers).json()
    assert late["refund_minor"] is None and late["cancel_at"] is not None


def test_a_bad_reason_is_rejected_and_only_the_owner_cancels(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    assert (
        client.post(
            "/billing/cancel", json={"reason": "bored"}, headers=studio["headers"]
        ).status_code
        == 422
    )
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    headers = auth(manager, studio["tenant_id"])
    assert client.post("/billing/pause", json={"months": 1}, headers=headers).status_code == 403
    assert client.get("/billing/cancel", headers=headers).status_code == 403


def test_a_pause_is_read_only_and_billed_at_the_flat_fee(
    client: TestClient, studio: dict, engine: Engine, monkeypatch
) -> None:
    outbox = Outbox()
    monkeypatch.setattr("app.api.subscription.sender_from_settings", lambda: outbox)
    headers = studio["headers"]
    # Not while the trial runs.
    assert (
        client.post("/billing/pause", json={"months": 1}, headers=headers).json()["detail"]
        == "in_trial"
    )
    assert client.get("/billing/cancel", headers=headers).json()["pause_available"] is False

    end_trial(engine, studio["tenant_id"], days_ago=40)
    assert run_billing(engine) == 1
    [invoice] = client.get("/billing", headers=headers).json()["invoices"]
    client.post("/billing/payment-method", json={"brand": "visa"}, headers=headers)
    client.post(f"/billing/invoices/{invoice['id']}/pay", headers=headers)

    offer = client.get("/billing/cancel", headers=headers).json()
    assert offer["pause_fee_minor"] == PAUSE_FEE["ILS"] and offer["pause_max_months"] == 3
    assert offer["pause_available"] is True and offer["refund_minor"] == invoice["total"]
    assert client.post("/billing/pause", json={"months": 4}, headers=headers).status_code == 422

    paused = client.post(
        "/billing/pause", json={"months": 2, "reason": "not_using"}, headers=headers
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["paused_until"] is not None and paused.json()["state"] == "read_only"
    assert len(outbox.sent) == 1
    # Everything can be seen, nothing changed; the billing page still works.
    assert client.get("/services", headers=headers).status_code == 200
    assert (
        client.post(
            "/services", json={"name": "Yoga", "duration_minutes": 60}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post("/billing/pause", json={"months": 1}, headers=headers).json()["detail"]
        == "already_paused"
    )

    # Periods that start inside the pause cost the flat fee.
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.tenants SET trial_ends_at = now() - interval '70 days',
                       pause_from = now() - interval '45 days'
                WHERE id = :t
            """),
            {"t": studio["tenant_id"]},
        )
        connection.execute(
            text("DELETE FROM app.platform_invoices WHERE tenant_id = :t"),
            {"t": studio["tenant_id"]},
        )
    assert run_billing(engine) >= 1
    with engine.begin() as connection:
        lines = (
            connection.execute(
                text(
                    "SELECT lines FROM app.platform_invoices "
                    "WHERE tenant_id = :t ORDER BY period_start"
                ),
                {"t": studio["tenant_id"]},
            )
            .scalars()
            .all()
        )
    assert lines[0][0]["key"] == "core"  # before the pause: the normal price
    assert lines[-1] == [{"key": "pause", "quantity": 1, "amount": PAUSE_FEE["ILS"]}]

    ended = client.delete("/billing/pause", headers=headers)
    assert ended.status_code == 200 and ended.json()["paused_until"] is None
    assert (
        client.post(
            "/services", json={"name": "Yoga", "duration_minutes": 60}, headers=headers
        ).status_code
        == 201
    )


def test_the_console_sees_cancellations_and_the_churn_months(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    client.post(
        "/billing/cancel",
        json={"reason": "switched", "note": "moved to a rival"},
        headers=studio["headers"],
    )
    admin = uuid4()
    client.get("/me", headers=auth(admin))
    assert client.get("/platform/billing/cancellations", headers=auth(admin)).status_code == 403
    make_staff(engine, admin)

    [row] = client.get("/platform/billing/cancellations", headers=auth(admin)).json()
    assert (
        row["name"] == "Studio Flow"
        and row["reason"] == "switched"
        and row["outcome"] == "cancelled"
    )
    months = client.get("/platform/billing/churn", headers=auth(admin)).json()
    assert len(months) == 12 and months[-1]["cancelled"] == 1 and months[-1]["paused"] == 0


def test_the_billing_job_still_ignores_unpaused_accounts(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    end_trial(engine, studio["tenant_id"], days_ago=35)
    with engine.begin() as connection:
        assert bill_businesses(connection, datetime.now(UTC)) == 1
    [line] = client.get("/billing", headers=studio["headers"]).json()["invoices"]
    invoice = client.get(f"/billing/invoices/{line['id']}", headers=studio["headers"]).json()
    assert invoice["lines"][0]["key"] == "core"
