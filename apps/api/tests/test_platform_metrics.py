"""SaaS numbers and email deliverability in the MyBiz console (K3)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, make_staff
from tests.test_billing import end_trial, run_billing


def staff(engine: Engine, auth: AuthHeaders, *permissions: str) -> dict:
    user = uuid4()
    make_staff(engine, user, "employee", tuple(permissions))
    return auth(user)


def test_metrics_need_console_permissions(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    assert client.get("/platform/metrics/saas", headers=studio["headers"]).status_code == 403
    assert client.get("/platform/metrics/email", headers=studio["headers"]).status_code == 403
    reader = staff(engine, auth, "usage.read")
    assert client.get("/platform/metrics/email", headers=reader).status_code == 200
    assert client.get("/platform/metrics/saas", headers=reader).status_code == 403
    biller = staff(engine, auth, "billing.manage")
    answer = client.get("/platform/metrics/saas", headers=biller)
    assert answer.status_code == 200 and answer.json()["ai"] is None
    assert client.get("/platform/metrics/email", headers=biller).status_code == 403


def test_saas_numbers_follow_the_billed_invoices(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    headers = staff(engine, auth, "billing.manage", "usage.read")
    empty = client.get("/platform/metrics/saas", headers=headers).json()
    assert empty["currencies"] == [] and empty["ai"]["margin_usd_minor"] == 0

    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    board = client.get("/platform/metrics/saas", headers=headers).json()
    [ils] = board["currencies"]
    due = client.get("/billing", headers=studio["headers"]).json()["balance_due"]
    assert ils["currency"] == "ILS" and ils["mrr"] == due > 0
    assert ils["arr"] == ils["mrr"] * 12 and ils["arpu"] == ils["mrr"]
    assert ils["months"][-1]["billed"] == ils["mrr"]
    assert board["churn"]["cancelled"] == 0


def test_deliverability_lists_masked_bounces(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    headers = staff(engine, auth, "usage.read")
    with engine.begin() as connection:
        connection.execute(text("SELECT app.suppress_email('Gone@Example.com', 'bounced', 'e1')"))
        connection.execute(text("SELECT app.suppress_email('spam@x.org', 'complained', 'e2')"))
    board = client.get("/platform/metrics/email", headers=headers).json()
    assert (board["bounced"], board["complained"]) == (1, 1)
    assert {r["address"] for r in board["recent"]} == {"g***@example.com", "s***@x.org"}
    assert sum(m["bounced"] + m["complained"] for m in board["months"]) == 2
    assert board["webhook_open"] is False
