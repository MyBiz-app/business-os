from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.announcements import send_announcements
from app.messaging.email import LogSender
from tests.conftest import AuthHeaders
from tests.test_migration import CLIENTS, add, start, upload_all

NOTICE = {
    "subject": "We moved to MyBiz",
    "body": "Hi {first_name}, {business} moved! Join with code {join_code}: {app_link}",
    "channels": ["email"],
}


def imported(client: TestClient, headers: dict) -> str:
    session = start(client, headers)
    add(client, headers, session, "clients.csv", CLIENTS)
    assert client.post(f"/migration/sessions/{session}/import", headers=headers).status_code == 200
    return session


def scalar(engine: Engine, sql: str, **params: object):
    with engine.connect() as connection:
        return connection.execute(text(sql), params).scalar_one()


def test_follow_up_counts_who_can_be_told(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session = imported(client, headers)
    data = client.get(f"/migration/sessions/{session}/follow-up", headers=headers).json()
    assert (data["clients"], data["with_email"], data["with_phone_only"]) == (2, 1, 1)
    assert data["notice_sent_at"] is None and data["concierge_requested_at"] is None


def test_dry_run_sends_nothing_and_phone_only_clients_get_whatsapp_links(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = imported(client, headers)
    response = client.post(f"/migration/sessions/{session}/notice", json=NOTICE, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["recipients"], data["clients"], data["sent"]) == (1, 2, False)
    assert data["by_channel"] == {"email": 1}
    assert "Dana" in data["preview"] and "Studio Flow" in data["preview"]
    assert data["phone_only_total"] == 1
    link = data["phone_only"][0]
    assert link["whatsapp_link"].startswith("https://wa.me/972521112233?text=")
    assert "Yossi" in link["text"]
    assert scalar(engine, "SELECT count(*) FROM app.announcements") == 0
    assert scalar(engine, "SELECT count(*) FROM app.messages") == 0


def test_the_notice_goes_out_as_a_service_email_once(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = imported(client, headers)
    url = f"/migration/sessions/{session}/notice"
    sent = client.post(url, json={**NOTICE, "dry_run": False}, headers=headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent"] is True
    assert scalar(engine, "SELECT count(*) FROM app.announcements WHERE kind = 'service'") == 1
    assert scalar(engine, "SELECT count(*) FROM app.messages") == 0  # no WhatsApp / SMS

    again = client.post(url, json={**NOTICE, "dry_run": False}, headers=headers)
    assert again.status_code == 409 and again.json()["detail"] == "already_sent"
    forced = client.post(url, json={**NOTICE, "dry_run": False, "resend": True}, headers=headers)
    assert forced.status_code == 200

    follow = client.get(f"/migration/sessions/{session}/follow-up", headers=headers).json()
    assert follow["notice_sent_at"] and follow["notice_recipients"] == 1

    # The email engine delivers it through the platform's provider (a log here), only to Dana.
    sender = LogSender()
    with engine.begin() as connection:
        send_announcements(connection, sender, None)
    assert [mail.to for mail in sender.sent] == ["dana@example.com", "dana@example.com"]
    assert "Studio Flow" in sender.sent[0].text and "Ad:" not in sender.sent[0].subject


def test_an_undone_move_has_nobody_to_tell(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session = imported(client, headers)
    batch = client.get(f"/migration/sessions/{session}", headers=headers).json()["batches"][0]
    undo = client.post(
        f"/migration/batches/{batch['id']}/undo", json={"include_edited": True}, headers=headers
    )
    assert undo.status_code == 200
    response = client.post(f"/migration/sessions/{session}/notice", json=NOTICE, headers=headers)
    assert response.status_code == 422 and response.json()["detail"] == "no_clients"


def test_only_email_push_and_popup_exist(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session = imported(client, headers)
    for channel in ("whatsapp", "sms"):
        response = client.post(
            f"/migration/sessions/{session}/notice",
            json={**NOTICE, "channels": [channel]},
            headers=headers,
        )
        assert response.status_code == 422


def test_concierge_opens_one_inbox_task_and_lets_support_in(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = start(client, headers)
    nothing = client.post(f"/migration/sessions/{session}/concierge", json={}, headers=headers)
    assert nothing.status_code == 422 and nothing.json()["detail"] == "no_files"

    add(client, headers, session, "clients.csv", CLIENTS)
    response = client.post(
        f"/migration/sessions/{session}/concierge",
        json={"note": "Please start with the clients", "support_hours": 24},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["included"] is False
    with engine.connect() as connection:
        request = connection.execute(
            text(
                "SELECT message, tenant_id FROM app.contact_requests "
                "WHERE message LIKE '[migration]%'"
            )
        ).one()
    assert session in request.message and "Please start with the clients" in request.message
    assert request.tenant_id == UUID(str(studio["tenant_id"]))
    assert scalar(engine, "SELECT count(*) FROM app.support_grants WHERE revoked_at IS NULL") == 1

    again = client.post(f"/migration/sessions/{session}/concierge", json={}, headers=headers)
    assert again.status_code == 409 and again.json()["detail"] == "already_requested"
    follow = client.get(f"/migration/sessions/{session}/follow-up", headers=headers).json()
    assert follow["concierge_requested_at"] and follow["support_until"]


def test_staff_and_strangers_are_kept_out(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session = upload_all(client, studio["headers"])
    coach = auth(studio["coach"], studio["tenant_id"])
    for method, path, body in (
        ("get", "follow-up", None),
        ("post", "notice", NOTICE),
        ("post", "concierge", {}),
    ):
        response = client.request(
            method, f"/migration/sessions/{session}/{path}", json=body, headers=coach
        )
        assert response.status_code == 403, path
