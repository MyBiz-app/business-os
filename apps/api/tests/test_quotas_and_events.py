"""Plan quota alerts and product events (go-live, GL21)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.commerce.modules import ALLOWANCES, Allowance
from tests.conftest import STUDIO, AuthHeaders, make_staff
from tests.test_documents_time import PDF, upload


def alerts(client: TestClient, headers: dict) -> list[tuple[str, int]]:
    usage = client.get("/billing/usage", headers=headers).json()
    return [(a["meter"], a["threshold"]) for a in usage["alerts"]]


def test_space_alerts_are_raised_once_at_80_and_100(
    client: TestClient, studio: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = studio["headers"]
    monkeypatch.setitem(ALLOWANCES, None, Allowance(storage_bytes=len(PDF) * 5, messages=200))
    assert alerts(client, headers) == []
    dana = client.post("/clients", json={"first_name": "Dana"}, headers=headers).json()["id"]
    for number in range(4):
        upload(client, headers, dana, f"f{number}.pdf")
    assert alerts(client, headers) == [("storage", 80)]
    upload(client, headers, dana, "five.pdf")
    assert alerts(client, headers) == [("storage", 80), ("storage", 100)]
    # Raised once: reading again changes nothing, and nothing else is blocked but new uploads.
    assert alerts(client, headers) == [("storage", 80), ("storage", 100)]


def test_message_alerts_never_block_messages(
    client: TestClient, studio: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = studio["headers"]
    monkeypatch.setitem(ALLOWANCES, None, Allowance(storage_bytes=1024**3, messages=2))
    client.put("/tenants/current/modules", json={"modules": {"whatsapp": 1}}, headers=headers)
    dana = client.post(
        "/clients", json={"first_name": "Dana", "phone": "050-1111111"}, headers=headers
    ).json()["id"]
    for _ in range(3):
        sent = client.post(
            "/messages/direct", json={"client_id": dana, "body": "Hi"}, headers=headers
        )
        assert sent.status_code == 201, sent.text
    assert alerts(client, headers) == [("messages", 80), ("messages", 100)]


def test_an_alert_belongs_to_its_business(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    other = uuid4()
    tenant = client.post("/tenants", json=STUDIO, headers=auth(other)).json()["id"]
    assert alerts(client, auth(other, tenant)) == []


def test_storage_counts_pictures_not_only_documents(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    before = client.get("/billing/usage", headers=headers).json()["storage_bytes"]
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0"
        b"\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = client.put(
        "/tenants/current/logo", files={"file": ("logo.png", png, "image/png")}, headers=headers
    )
    assert response.status_code in (200, 201), response.text
    after = client.get("/billing/usage", headers=headers).json()["storage_bytes"]
    assert after == before + len(png)


def test_signup_steps_need_no_sign_in_and_hold_no_personal_data(
    client: TestClient, engine: Engine
) -> None:
    visitor = str(uuid4())
    for body in (
        {"visitor_id": visitor, "event": "signup_started"},
        {"visitor_id": visitor, "event": "signup_step", "step": "industry"},
    ):
        assert client.post("/public/events", json=body).status_code == 204
    # Only the known events and steps are accepted.
    for body in (
        {"visitor_id": visitor, "event": "signup_completed"},
        {"visitor_id": visitor, "event": "signup_step", "step": "email_me@example.com"},
    ):
        assert client.post("/public/events", json=body).status_code == 422
    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT event, step, tenant_id FROM app.product_events ORDER BY id")
        ).all()
    assert rows == [("signup_started", None, None), ("signup_step", "industry", None)]


def test_the_console_sees_the_funnel_activity_and_biggest_consumers(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    visitor = uuid4()
    for body in (
        {"visitor_id": str(visitor), "event": "signup_started"},
        {"visitor_id": str(visitor), "event": "signup_step", "step": "industry"},
        {"visitor_id": str(uuid4()), "event": "signup_started"},
    ):
        client.post("/public/events", json=body)
    owner = uuid4()
    created = client.post("/tenants", json=STUDIO, headers=auth(owner))
    assert created.status_code == 201, created.text
    headers = auth(owner, created.json()["id"])
    client.post("/clients", json={"first_name": "Dana"}, headers=headers)
    client.put("/tenants/current/modules", json={"modules": {"whatsapp": 1}}, headers=headers)
    # An ordinary business owner has no console access.
    assert client.get("/platform/funnel", headers=headers).status_code == 403

    admin = uuid4()
    make_staff(engine, admin, "owner", ())
    console = auth(admin)
    funnel = {
        s["key"]: s["visitors"] for s in client.get("/platform/funnel", headers=console).json()
    }
    assert funnel["started"] == 2 and funnel["industry"] == 1 and funnel["completed"] == 1
    assert funnel["summary"] == 0

    days = client.get("/platform/activity?days=7", headers=console).json()
    assert len(days) == 7 and days[-1]["active_day"] == 1 and days[-1]["active_week"] == 1

    top = client.get("/platform/top-consumers", headers=console).json()
    assert [row["name"] for row in top] == [STUDIO["name"]]

    with engine.begin() as connection:
        events = {
            row[0]
            for row in connection.execute(
                text("SELECT event FROM app.product_events WHERE tenant_id IS NOT NULL")
            )
        }
    assert events >= {"signup_completed", "first_client", "module_enabled"}
