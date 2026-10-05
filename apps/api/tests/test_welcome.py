from datetime import date

from fastapi.testclient import TestClient

from app.welcome import WelcomeDetails, build_welcome


def details(**overrides: object) -> WelcomeDetails:
    values: dict = {
        "to": "owner@example.com",
        "business": "Studio <Flow>",
        "locale": "en",
        "currency": "ILS",
        "join_code": "ABC123",
        "trial_ends_on": date(2026, 10, 19),
        "modules": {"client_app": 1, "extra_location": 2},
        "expected_active_clients": 250,
        "web_url": "https://app.example.com",
        "client_app_url": "https://go.example.com",
        "simulated": True,
    }
    values.update(overrides)
    return WelcomeDetails(**values)


def test_welcome_email_lists_the_plan_and_links() -> None:
    email = build_welcome(details())
    assert email.to == "owner@example.com"
    assert "Studio <Flow>" in email.subject
    # Core for up to 300 active clients, the client app and two extra locations.
    assert "₪149" in email.text and "₪49" in email.text and "₪58" in email.text
    assert "₪256" in email.text
    assert "Oct 19, 2026" in email.text
    assert "ABC123" in email.text
    assert "https://go.example.com/join?code=ABC123" in email.text
    assert "https://app.example.com/getting-started" in email.text
    assert email.html is not None
    assert "Studio &lt;Flow&gt;" in email.html and "<Flow>" not in email.html
    assert 'dir="ltr"' in email.html


def test_welcome_email_in_hebrew_is_right_to_left() -> None:
    email = build_welcome(details(locale="he", modules={}))
    assert email.html is not None and 'dir="rtl"' in email.html
    assert "19/10/2026" in email.text and "149 ₪" in email.text


def test_the_welcome_email_is_sent_once(client: TestClient, studio: dict, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("API_EMAIL_PROVIDER", "log")
    get_settings.cache_clear()
    try:
        headers = studio["headers"]
        preview = client.get("/tenants/current/welcome-email", headers=headers).json()
        assert preview["status"] == "preview" and preview["html"].startswith("<!doctype html>")
        first = client.post(
            "/tenants/current/welcome-email", json={"expected_active_clients": 80}, headers=headers
        ).json()
        assert first["status"] == "logged"
        again = client.post("/tenants/current/welcome-email", json={}, headers=headers).json()
        assert again["status"] == "already_sent"
    finally:
        get_settings.cache_clear()


def test_only_the_owner_side_can_send_it(client: TestClient, studio: dict, auth) -> None:
    staff = auth(studio["coach"], studio["tenant_id"])
    assert client.post("/tenants/current/welcome-email", json={}, headers=staff).status_code == 403
