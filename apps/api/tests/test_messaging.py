from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders
from tests.test_client_app import give_plan


def with_messaging(client: TestClient, headers: dict, *extra: str) -> None:
    modules = {"whatsapp": 1, **dict.fromkeys(extra, 1)}
    response = client.put("/tenants/current/modules", json={"modules": modules}, headers=headers)
    assert response.status_code == 200, response.text


def add_client(client: TestClient, headers: dict, name: str, phone: str | None) -> str:
    return client.post(
        "/clients", json={"first_name": name, "phone": phone}, headers=headers
    ).json()["id"]


def test_messaging_needs_the_module(client: TestClient, studio: dict) -> None:
    response = client.get("/messages/audiences", headers=studio["headers"])
    assert response.status_code == 403 and response.json()["detail"] == "module_disabled"


def test_broadcast_to_a_segment(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    dana = add_client(client, headers, "Dana", "050-1111111")
    add_client(client, headers, "Noa", "050-2222222")
    add_client(client, headers, "NoPhone", None)
    give_plan(client, studio, dana)

    counts = {
        a["audience"]: a["recipients"]
        for a in client.get("/messages/audiences", headers=headers).json()
    }
    assert counts["active"] == 2 and counts["no_plan"] == 1
    assert "open_leads" not in counts  # needs the CRM module

    body = {"audience": "active", "body": "Hi {first_name}, news from {business}!"}
    preview = client.post("/messages/campaigns", json={**body, "dry_run": True}, headers=headers)
    assert preview.json() == {
        "id": None,
        "recipients": 2,
        "preview": "Hi Dana, news from Studio Flow!",
    }

    sent = client.post("/messages/campaigns", json=body, headers=headers).json()
    assert sent["id"] and sent["recipients"] == 2
    log = client.get("/messages", params={"campaign_id": sent["id"]}, headers=headers).json()
    assert sorted(m["body"] for m in log) == [
        "Hi Dana, news from Studio Flow!",
        "Hi Noa, news from Studio Flow!",
    ]
    assert all(m["simulated"] and m["status"] == "sent" for m in log)
    [campaign] = client.get("/messages/campaigns", headers=headers).json()
    assert campaign["recipients"] == 2
    with engine.connect() as connection:
        used = connection.execute(
            text("SELECT sum(quantity) FROM app.usage_events WHERE meter = 'messages'")
        ).scalar_one()
    assert used == 2


def test_direct_messages_and_templates(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers, "crm")
    dana = add_client(client, headers, "Dana", "050-1111111")
    silent = add_client(client, headers, "Silent", None)
    lead = client.post(
        "/leads", json={"first_name": "Lior", "phone": "052-3333333"}, headers=headers
    ).json()

    to_client = client.post(
        "/messages/direct",
        json={"client_id": dana, "body": "See you, {first_name}"},
        headers=headers,
    )
    assert to_client.status_code == 201, to_client.text
    assert to_client.json()["body"] == "See you, Dana"
    to_lead = client.post(
        "/messages/direct",
        json={"lead_id": lead["id"], "body": "Hello", "channel": "sms"},
        headers=headers,
    )
    assert to_lead.json()["recipient_name"] == "Lior" and to_lead.json()["channel"] == "sms"
    no_phone = client.post(
        "/messages/direct", json={"client_id": silent, "body": "x"}, headers=headers
    )
    assert no_phone.status_code == 409
    both = client.post(
        "/messages/direct",
        json={"client_id": dana, "lead_id": lead["id"], "body": "x"},
        headers=headers,
    )
    assert both.status_code == 422
    assert len(client.get("/messages", params={"client_id": dana}, headers=headers).json()) == 1
    counts = {
        a["audience"]: a["recipients"]
        for a in client.get("/messages/audiences", headers=headers).json()
    }
    assert counts["open_leads"] == 1

    template = client.post(
        "/messages/templates", json={"name": "Reminder", "body": "Hi {first_name}"}, headers=headers
    ).json()
    assert [t["name"] for t in client.get("/messages/templates", headers=headers).json()] == [
        "Reminder"
    ]
    assert (
        client.delete(f"/messages/templates/{template['id']}", headers=headers).status_code == 204
    )


def test_staff_can_read_but_not_send(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    with_messaging(client, studio["headers"])
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/messages", headers=coach).status_code == 200
    sent = client.post(
        "/messages/campaigns", json={"audience": "active", "body": "x"}, headers=coach
    )
    assert sent.status_code == 403


def test_privacy_covers_messages(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    dana = add_client(client, headers, "Dana", "050-1111111")
    client.post("/messages/direct", json={"client_id": dana, "body": "Hi"}, headers=headers)
    document = client.get(f"/clients/{dana}/export", headers=headers).json()
    assert [m["body"] for m in document["messages"]] == ["Hi"]
    client.post(f"/clients/{dana}/erase", json={"confirm": True}, headers=headers)
    assert client.get("/messages", params={"client_id": dana}, headers=headers).json() == []
