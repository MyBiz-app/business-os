"""Two-step sign-in (GL1): the assurance level in the token, the gates, and new-device emails."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api.devices import get_sender
from app.core import config
from app.core.mfa import RISK_VERSION
from app.main import create_app  # noqa: F401  (the client fixture builds the app)
from app.messaging.email import Email
from tests.conftest import AuthHeaders, add_member, make_staff


@pytest.fixture
def mfa_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("API_MFA_ENFORCED", "true")
    config.get_settings.cache_clear()
    yield
    monkeypatch.undo()
    config.get_settings.cache_clear()


def test_enforcement_is_on_outside_local_development() -> None:
    assert config.Settings(environment="local").mfa_on is False
    assert config.Settings(environment="staging").mfa_on is True
    assert config.Settings(environment="production", mfa_enforced=False).mfa_on is False


def test_the_console_needs_a_code(
    client: TestClient, engine: Engine, auth: AuthHeaders, mfa_on: None
) -> None:
    staff = uuid4()
    make_staff(engine, staff)
    refused = client.get("/platform/staff", headers=auth(staff, aal="aal1"))
    assert refused.status_code == 403 and refused.json()["detail"] == "mfa_required"
    assert client.get("/platform/staff", headers=auth(staff)).status_code == 403  # no claim: aal1
    assert client.get("/platform/staff", headers=auth(staff, aal="aal2")).status_code == 200
    # Being signed in without a code is still enough to see who one is (to be sent to set it up).
    assert client.get("/me", headers=auth(staff, aal="aal1")).status_code == 200


def test_someone_who_is_not_on_the_team_is_simply_refused(
    client: TestClient, auth: AuthHeaders, mfa_on: None
) -> None:
    response = client.get("/platform/staff", headers=auth(uuid4(), aal="aal2"))
    assert response.status_code == 403 and response.json()["detail"] == "forbidden"


def test_a_business_can_require_a_code_of_its_team(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders, mfa_on: None
) -> None:
    coach = uuid4()
    add_member(engine, studio["tenant_id"], coach, "staff")
    assert (
        client.get("/tenants/current", headers=auth(coach, studio["tenant_id"])).status_code == 200
    )

    owner = studio["headers"]
    owner_id = client.get("/me", headers=owner).json()["id"]
    on = client.patch(
        "/tenants/current",
        json={"require_mfa_for_staff": True},
        headers=auth(owner_id, studio["tenant_id"], aal="aal2"),
    )
    assert on.status_code == 200 and on.json()["require_mfa_for_staff"] is True

    blocked = client.get("/tenants/current", headers=auth(coach, studio["tenant_id"], aal="aal1"))
    assert blocked.status_code == 403 and blocked.json()["detail"] == "mfa_required"
    allowed = client.get("/tenants/current", headers=auth(coach, studio["tenant_id"], aal="aal2"))
    assert allowed.status_code == 200


def test_owners_must_confirm_the_risk_before_a_sensitive_action(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal1")
    body = {"cancellation_window_minutes": 60}
    # Everyday work needs no code ...
    assert client.get("/services", headers=headers).status_code == 200
    # ... settings need a code or the confirmed warning.
    refused = client.patch("/tenants/current", json=body, headers=headers)
    assert refused.status_code == 403 and refused.json()["detail"] == "mfa_risk_ack_required"
    assert client.get("/me/security", headers=headers).json()["mfa_risk_acknowledged"] is False

    assert client.post("/me/security/mfa-risk-acknowledgement", headers=headers).status_code == 204
    assert client.post("/me/security/mfa-risk-acknowledgement", headers=headers).status_code == 204
    assert client.get("/me/security", headers=headers).json()["mfa_risk_acknowledged"] is True
    assert client.patch("/tenants/current", json=body, headers=headers).status_code == 200

    with engine.connect() as connection:  # one row per person and version, with the time
        rows = connection.execute(
            text("SELECT version FROM app.mfa_risk_acknowledgements WHERE user_id = :user"),
            {"user": owner_id},
        ).all()
    assert [row.version for row in rows] == [RISK_VERSION]
    # Someone else's confirmation does not count for this person.
    other = uuid4()
    add_member(engine, studio["tenant_id"], other, "manager")
    stranger = auth(other, studio["tenant_id"], aal="aal1")
    assert client.patch("/tenants/current", json=body, headers=stranger).status_code == 403


def test_a_code_needs_no_confirmation(
    client: TestClient, studio: dict, auth: AuthHeaders, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal2")
    body = {"cancellation_window_minutes": 60}
    assert client.patch("/tenants/current", json=body, headers=headers).status_code == 200


def test_the_confirmation_is_in_the_audit_log(
    client: TestClient, studio: dict, auth: AuthHeaders, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal1")
    client.post("/me/security/mfa-risk-acknowledgement", headers=headers)
    log = client.get("/audit-log", headers=headers)
    assert log.status_code == 200, log.text
    assert "mfa.risk_acknowledged" in [entry["action"] for entry in log.json()["entries"]]


def test_the_confirmation_keeps_where_it_was_given(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal1")
    path = "/me/security/mfa-risk-acknowledgement"
    assert client.post(path, json={"source": "anywhere"}, headers=headers).status_code == 422
    assert client.post(path, json={"source": "opt_out"}, headers=headers).status_code == 204
    # A second confirmation of the same version keeps the first one.
    assert client.post(path, json={"source": "sensitive_action"}, headers=headers).status_code == 204
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT version, source, user_agent FROM app.mfa_risk_acknowledgements
                WHERE user_id = :user
            """),
            {"user": owner_id},
        ).all()
    assert [(row.version, row.source) for row in rows] == [(RISK_VERSION, "opt_out")]
    log = client.get("/audit-log", headers=headers).json()["entries"]
    confirmed = [entry for entry in log if entry["action"] == "mfa.risk_acknowledged"]
    assert confirmed and confirmed[0]["details"]["source"] in {"opt_out", "sensitive_action"}


def test_remind_me_in_a_week_does_not_open_sensitive_actions(
    client: TestClient, studio: dict, auth: AuthHeaders, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal1")
    assert client.get("/me/security", headers=headers).json()["mfa_reminder_snoozed_until"] is None
    assert client.post("/me/reminders/mfa/snooze", headers=headers).status_code == 204
    policy = client.get("/me/security", headers=headers).json()
    until = datetime.fromisoformat(policy["mfa_reminder_snoozed_until"])
    assert timedelta(days=6, hours=23) < until - datetime.now(UTC) <= timedelta(days=7)
    assert policy["mfa_risk_acknowledged"] is False
    body = {"cancellation_window_minutes": 60}
    refused = client.patch("/tenants/current", json=body, headers=headers)
    assert refused.status_code == 403 and refused.json()["detail"] == "mfa_risk_ack_required"


def test_the_home_address_reminder_can_be_skipped(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    me = client.get("/me", headers=headers).json()
    assert me["address_complete"] is False and me["address_reminder_skipped"] is False
    assert client.post("/me/reminders/address/skip", headers=headers).status_code == 204
    assert client.post("/me/reminders/address/skip", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).json()["address_reminder_skipped"] is True


def test_demo_exemption_is_staging_only_and_by_email() -> None:
    emails = "demo@example.com, Other@Example.com"
    staging = config.Settings(environment="staging", mfa_demo_exempt_emails=emails)
    assert staging.mfa_exempt("demo@example.com")
    assert staging.mfa_exempt("other@example.com")
    assert not staging.mfa_exempt("someone@example.com")
    assert not staging.mfa_exempt("")
    assert not config.Settings(environment="staging").mfa_exempt("demo@example.com")
    for environment in ("production", "local", "test"):
        settings = config.Settings(environment=environment, mfa_demo_exempt_emails=emails)
        assert not settings.mfa_exempt("demo@example.com")


def test_an_exempt_demo_owner_is_not_asked_for_a_code(
    client: TestClient,
    studio: dict,
    auth: AuthHeaders,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
    mfa_on: None,
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    path, body = "/tenants/current", {"cancellation_window_minutes": 60}
    exempt = {"Authorization": f"Bearer {make_token(owner_id, email='demo@example.com')}"}
    exempt["X-Tenant-Id"] = str(studio["tenant_id"])

    # Not on the list: the sensitive action still needs a code.
    assert client.patch(path, json=body, headers=exempt).status_code == 403
    monkeypatch.setenv("API_MFA_DEMO_EXEMPT_EMAILS", "demo@example.com")
    monkeypatch.setattr(
        config.Settings, "mfa_exempt", lambda _s, email: email == "demo@example.com"
    )
    config.get_settings.cache_clear()
    assert client.patch(path, json=body, headers=exempt).status_code == 200
    # The same person under another email, or anyone else, is unaffected.
    other = auth(owner_id, studio["tenant_id"], aal="aal1")
    assert client.patch(path, json=body, headers=other).json()["detail"] == "mfa_risk_ack_required"


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


@pytest.fixture
def outbox(client: TestClient) -> Outbox:
    box = Outbox()
    client.app.dependency_overrides[get_sender] = lambda: box
    return box


def check(client: TestClient, headers: dict, device: str, label: str = "Chrome on Windows"):
    return client.post(
        "/me/devices/check",
        json={"device_id": device, "label": label, "locale": "en"},
        headers=headers,
    )


def test_a_new_device_is_emailed_but_the_first_one_and_known_ones_are_not(
    client: TestClient, auth: AuthHeaders, outbox: Outbox
) -> None:
    headers = auth(uuid4())
    first = check(client, headers, "a" * 32)
    assert first.json() == {"new_device": True}
    assert outbox.sent == []  # the very first device is the person signing up

    assert check(client, headers, "a" * 32).json() == {"new_device": False}
    assert outbox.sent == []

    second = check(client, headers, "b" * 32, "Safari on iPhone")
    assert second.json() == {"new_device": True}
    assert len(outbox.sent) == 1
    email = outbox.sent[0]
    assert ("Device", "Safari on iPhone") in email.details
    assert "new" in email.subject.lower()


def test_devices_are_listed_for_their_owner_only(
    client: TestClient, auth: AuthHeaders, outbox: Outbox, engine: Engine
) -> None:
    me, other = auth(uuid4()), auth(uuid4())
    check(client, me, "a" * 32, "Chrome")
    check(client, me, "b" * 32, "Firefox")
    check(client, other, "c" * 32, "Edge")
    listing = client.get("/me/devices", headers={**me, "X-Device-Id": "b" * 32}).json()
    assert {d["label"] for d in listing} == {"Chrome", "Firefox"}
    assert [d["label"] for d in listing if d["current"]] == ["Firefox"]
    with engine.connect() as connection:  # only a hash is kept, never the device id
        stored = (
            connection.execute(text("SELECT device_hash FROM app.login_devices")).scalars().all()
        )
    assert "a" * 32 not in stored and all(len(h) == 64 for h in stored)


def test_an_email_that_fails_does_not_fail_the_sign_in(
    client: TestClient, auth: AuthHeaders
) -> None:
    class Broken:
        def send(self, email: Email) -> None:
            raise RuntimeError("smtp down")

    client.app.dependency_overrides[get_sender] = lambda: Broken()
    headers = auth(uuid4())
    check(client, headers, "a" * 32)
    assert check(client, headers, "b" * 32).status_code == 200
