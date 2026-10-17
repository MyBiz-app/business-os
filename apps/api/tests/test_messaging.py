from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.announcements import send_announcements
from app.messaging.email import LogSender
from tests.conftest import AuthHeaders, add_member
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
        "by_channel": {"whatsapp": 2},
        "preview": "Hi Dana, news from Studio Flow!",
        "warnings": [],
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


# --- Branch-targeted messages (round 5, F4) ---------------------------------------------------


def two_branches(client: TestClient, studio: dict) -> tuple[str, str]:
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=studio["headers"]).json()[
        "id"
    ]
    return north, south


def add_branch_client(
    client: TestClient, headers: dict, name: str, branch: str, **extra: str | None
) -> str:
    created = client.post(
        "/clients",
        json={"first_name": name, "home_location_id": branch, **extra},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_a_campaign_reaches_only_the_chosen_branches(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    north, south = two_branches(client, studio)
    add_branch_client(client, headers, "Dana", north, phone="050-1111111")
    add_branch_client(client, headers, "Noa", south, phone="050-2222222")
    add_branch_client(client, headers, "Eli", south, phone="050-3333333")

    def count(**extra: object) -> int:
        body = {"audience": "active", "body": "Hi", "dry_run": True, **extra}
        response = client.post("/messages/campaigns", json=body, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["recipients"]

    assert count() == 3  # the whole network
    assert count(location_ids=[north]) == 1
    assert count(location_ids=[south]) == 2
    assert count(location_ids=[north, south]) == 3
    live = client.get("/messages/audiences", params={"location_ids": [south]}, headers=headers)
    assert {a["audience"]: a["recipients"] for a in live.json()}["active"] == 2

    sent = client.post(
        "/messages/campaigns",
        json={"audience": "active", "body": "Hi {first_name}", "location_ids": [north]},
        headers=headers,
    ).json()
    log = client.get("/messages", params={"campaign_id": sent["id"]}, headers=headers).json()
    assert [m["body"] for m in log] == ["Hi Dana"]
    [campaign] = client.get("/messages/campaigns", headers=headers).json()
    assert campaign["location_ids"] == [north] and campaign["channels"] == ["whatsapp"]


def test_a_branch_must_be_the_businesses_own(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    body = {"audience": "active", "body": "Hi", "dry_run": True}
    bad = client.post(
        "/messages/campaigns", json={**body, "location_ids": [str(uuid4())]}, headers=headers
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "unknown_branch"
    empty = client.post("/messages/campaigns", json={**body, "location_ids": []}, headers=headers)
    assert empty.status_code == 422
    leads = client.post(
        "/messages/campaigns",
        json={**body, "audience": "open_leads", "location_ids": [studio["location"]["id"]]},
        headers=headers,
    )
    assert leads.status_code in (403, 422)  # leads belong to no branch


def test_email_and_pop_up_go_through_the_broadcast_engine(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    north, south = two_branches(client, studio)
    add_branch_client(client, headers, "Dana", north, email="dana@example.com")
    add_branch_client(client, headers, "Noa", south, email="noa@example.com")
    add_branch_client(client, headers, "NoMail", south, phone="050-4444444")

    body = {
        "audience": "active",
        "channels": ["email", "popup"],
        "location_ids": [south],
        "subject": "South opens late",
        "body": "Hi {first_name}, {business} South opens at 10.",
    }
    preview = client.post("/messages/campaigns", json={**body, "dry_run": True}, headers=headers)
    assert preview.json()["recipients"] == 1  # NoMail has neither an email nor an account
    assert preview.json()["by_channel"] == {"email": 1, "popup": 0}

    sent = client.post("/messages/campaigns", json=body, headers=headers)
    assert sent.status_code == 200, sent.text
    mail = LogSender()
    with engine.begin() as connection:
        send_announcements(connection, mail, None)
    [email] = mail.sent
    assert email.to == "noa@example.com" and email.subject == "South opens late"
    assert "Hi Noa, Studio Flow South opens at 10." in email.text
    assert email.from_name == "Studio Flow"
    with engine.connect() as connection:
        [issuer] = connection.execute(text("SELECT issuer FROM app.announcements")).scalars()
    assert issuer == "tenant"


def test_staff_of_some_branches_get_a_message(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    headers = studio["headers"]
    north, south = two_branches(client, studio)
    kept = uuid4()
    add_member(engine, studio["tenant_id"], kept, "front_desk")
    client.put(f"/staff/{kept}/branches", json={"location_ids": [south]}, headers=headers)

    def staff(**extra: object) -> dict:
        body = {"audience": "staff", "channels": ["email"], "body": "Roster", "dry_run": True}
        response = client.post("/messages/campaigns", json={**body, **extra}, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    everyone = staff()["recipients"]
    south_only = staff(location_ids=[south])["recipients"]
    north_only = staff(location_ids=[north])["recipients"]
    assert south_only == north_only + 1 and everyone >= south_only  # `kept` works only in South
    nothing = client.post(
        "/messages/campaigns",
        json={"audience": "staff", "channels": ["whatsapp"], "body": "x"},
        headers=headers,
    )
    assert nothing.status_code == 422 and nothing.json()["detail"] == "staff_channels"


def test_a_member_kept_to_a_branch_cannot_message_another(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    owner = studio["headers"]
    with_messaging(client, owner)
    north, south = two_branches(client, studio)
    add_branch_client(client, owner, "Dana", north, phone="050-1111111")
    add_branch_client(client, owner, "Noa", south, phone="050-2222222")
    kept = uuid4()
    add_member(engine, studio["tenant_id"], kept, "front_desk")
    client.put(f"/staff/{kept}/branches", json={"location_ids": [north]}, headers=owner)
    mine = auth(kept, studio["tenant_id"])
    body = {"audience": "active", "body": "Hi", "dry_run": True}
    response = client.post("/messages/campaigns", json=body, headers=mine)
    assert response.status_code == 200, response.text
    assert response.json()["recipients"] == 1  # by default only their own branch
    other = client.post("/messages/campaigns", json={**body, "location_ids": [south]}, headers=mine)
    assert other.status_code == 422 and other.json()["detail"] == "unknown_branch"


def test_placeholders_render_with_fallbacks_and_warnings(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    dana = add_client(client, headers, "Dana", "050-1111111")
    add_client(client, headers, "Noa", "050-2222222")
    give_plan(client, studio, dana)

    catalog = client.get("/messages/placeholders", headers=headers).json()
    assert [g["key"] for g in catalog["groups"]] == ["client", "plan", "booking", "business"]
    names = {v for g in catalog["groups"] for v in g["variables"]}
    assert "id_last4" in names and "id_number" not in names

    body = {
        "audience": "active",
        "dry_run": True,
        "body": (
            "{first_name} {last_name|friend}: {plan_name} / {plan_expires} {unknown|x} {id_number}"
        ),
    }
    result = client.post("/messages/campaigns", json=body, headers=headers).json()
    # Noa has no plan: plan_name and plan_expires have no fallback, so both are warned about.
    assert {w["variable"]: w["recipients"] for w in result["warnings"]} == {
        "plan_name": 1,
        "plan_expires": 1,
    }
    assert "friend" in result["preview"] and "{unknown|x} {id_number}" in result["preview"]

    sent = client.post(
        "/messages/campaigns", json={**body, "dry_run": False}, headers=headers
    ).json()
    log = client.get("/messages", params={"campaign_id": sent["id"]}, headers=headers).json()
    noa = next(m for m in log if m["body"].startswith("Noa"))
    assert noa["body"] == "Noa friend:  /  {unknown|x} {id_number}"
