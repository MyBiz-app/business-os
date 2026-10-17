"""Bounced and complained addresses are never mailed again (go-live GL22)."""

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import get_settings
from app.messaging.email import Email, LogSender, SuppressingSender

SECRET = "whsec_" + base64.b64encode(b"test-signing-key").decode()


@pytest.fixture
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_EMAIL_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def signed(payload: dict, stamp: int | None = None) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode()
    stamp = stamp or int(time.time())
    mac = hmac.new(b"test-signing-key", f"msg_1.{stamp}.".encode() + body, hashlib.sha256)
    return body, {
        "svix-id": "msg_1",
        "svix-timestamp": str(stamp),
        "svix-signature": "v1," + base64.b64encode(mac.digest()).decode(),
    }


def event(kind: str, bounce: str | None = None, to: str = "Gone@Example.com") -> dict:
    data: dict = {"email_id": "e1", "to": [to]}
    if bounce:
        data["bounce"] = {"type": bounce}
    return {"type": kind, "data": data}


def suppressed(engine: Engine, address: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(text("SELECT app.email_is_suppressed(:a)"), {"a": address}).scalar()
        )


def test_closed_until_the_secret_is_set(client: TestClient) -> None:
    body, headers = signed(event("email.complained"))
    assert client.post("/webhooks/email/resend", content=body, headers=headers).status_code == 404


def test_rejects_bad_and_old_signatures(client: TestClient, webhook_secret: None) -> None:
    body, headers = signed(event("email.complained"))
    headers["svix-signature"] = "v1,AAAA"
    assert client.post("/webhooks/email/resend", content=body, headers=headers).status_code == 401
    body, headers = signed(event("email.complained"), stamp=int(time.time()) - 3600)
    assert client.post("/webhooks/email/resend", content=body, headers=headers).status_code == 401


def test_hard_bounce_and_complaint_suppress(
    client: TestClient, engine: Engine, webhook_secret: None
) -> None:
    for payload in (
        event("email.bounced", "Permanent", "Gone@Example.com"),
        event("email.complained", to="angry@example.com"),
    ):
        body, headers = signed(payload)
        assert (
            client.post("/webhooks/email/resend", content=body, headers=headers).status_code == 204
        )
    assert suppressed(engine, "gone@example.com") and suppressed(engine, "angry@example.com")


def test_soft_bounce_and_delivery_do_not_suppress(
    client: TestClient, engine: Engine, webhook_secret: None
) -> None:
    for payload in (event("email.bounced", "Transient"), event("email.delivered")):
        body, headers = signed(payload)
        assert (
            client.post("/webhooks/email/resend", content=body, headers=headers).status_code == 204
        )
    assert not suppressed(engine, "gone@example.com")


def test_suppressed_address_is_not_mailed_and_shows_on_the_client(
    client: TestClient, engine: Engine, studio: dict, webhook_secret: None
) -> None:
    headers = studio["headers"]
    made = client.post(
        "/clients", json={"first_name": "Dana", "email": "dana@example.com"}, headers=headers
    )
    assert made.status_code == 201, made.text
    assert made.json()["email_suppressed"] is False
    body, sig = signed(event("email.bounced", "Permanent", "dana@example.com"))
    assert client.post("/webhooks/email/resend", content=body, headers=sig).status_code == 204
    shown = client.get(f"/clients/{made.json()['id']}", headers=headers).json()
    assert shown["email_suppressed"] is True

    inner = LogSender()
    sender = SuppressingSender(inner, lambda address: suppressed(engine, address))
    sender.send(Email(to="Dana@example.com", subject="s", text="t"))
    sender.send(Email(to="ok@example.com", subject="s", text="t"))
    assert [m.to for m in inner.sent] == ["ok@example.com"]
