from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.email import Email, LogSender, load_messages, send_emails
from tests.conftest import AuthHeaders
from tests.test_bookings import book, new_session
from tests.test_client_app import member


class FailingSender:
    def send(self, email: Email) -> None:
        raise RuntimeError("provider down")


def booked_member(client: TestClient, auth: AuthHeaders, studio: dict) -> str:
    joined = member(client, auth, studio, uuid4())
    client.patch(
        f"/clients/{joined['client_id']}",
        json={"email": f"dana{uuid4().hex[:6]}@example.com", "first_name": "Dana"},
        headers=studio["headers"],
    )
    book(client, studio["headers"], new_session(client, studio), joined["client_id"])
    return joined["client_id"]


def test_pending_notifications_are_emailed_once_in_the_business_language(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    booked_member(client, auth, studio)
    sender = LogSender()

    with engine.begin() as connection:
        first = send_emails(connection, sender)
    with engine.begin() as connection:
        again = send_emails(connection, sender)

    assert first == {"sent": 1, "failed": 0, "skipped": 0}
    assert again["sent"] == 0
    [email] = sender.sent
    assert email.to.startswith("dana")
    assert email.subject.startswith("נרשמת לPilates ב-")  # the studio is Hebrew
    assert email.text.startswith("שלום Dana,")
    assert "Studio Flow" in email.text
    with engine.connect() as connection:
        usage = connection.execute(
            text("""
                SELECT quantity, details->>'channel' FROM app.usage_events
                WHERE meter = 'messages'
            """)
        ).all()
    assert [(int(q), channel) for q, channel in usage] == [(1, "email")]


def test_old_notifications_and_clients_without_email_are_skipped(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    no_email = member(client, auth, studio, uuid4())["client_id"]
    client.patch(f"/clients/{no_email}", json={"email": None}, headers=studio["headers"])
    book(client, studio["headers"], new_session(client, studio), no_email)
    booked_member(client, auth, studio)

    with engine.begin() as connection:
        result = send_emails(connection, LogSender(), now=datetime.now(UTC) + timedelta(days=2))

    assert result == {"sent": 0, "failed": 0, "skipped": 2}


def test_failures_are_retried_then_given_up(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    booked_member(client, auth, studio)

    for _ in range(3):
        with engine.begin() as connection:
            assert send_emails(connection, FailingSender())["failed"] == 1
    with engine.begin() as connection:
        assert send_emails(connection, FailingSender())["failed"] == 0
        status = connection.execute(text("SELECT email_status FROM app.notifications")).scalar()
    assert status == "failed"


def test_every_notification_kind_has_email_text() -> None:
    from app.api.notifications import NotificationKind

    kinds = [*NotificationKind.__args__, "waitlisted_by_studio"]
    for locale in ("he", "en"):
        messages = load_messages(locale)
        assert set(messages["subject"]) == set(kinds)
        assert set(messages["body"]) == set(kinds)


def test_gmail_sender_signs_in_with_the_from_address(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.messaging.email import Email, SmtpSender, sender_from_settings

    monkeypatch.setenv("API_EMAIL_PROVIDER", "gmail")
    monkeypatch.setenv("API_EMAIL_API_KEY", "app-password")
    monkeypatch.setenv("API_EMAIL_FROM", "MyBiz <studio.mybiz@gmail.com>")
    get_settings.cache_clear()
    try:
        sender = sender_from_settings()
    finally:
        get_settings.cache_clear()

    assert isinstance(sender, SmtpSender)
    assert (sender.host, sender.port, sender.username) == (
        "smtp.gmail.com",
        465,
        "studio.mybiz@gmail.com",
    )
    message = sender.message(Email(to="dana@example.com", subject="שלום", text="שורה 1\nשורה 2"))
    assert message["From"] == "MyBiz <studio.mybiz@gmail.com>"
    assert "שורה 1<br>שורה 2" in message.get_body(("html",)).get_content()
