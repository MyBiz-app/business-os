"""Two-step sign-in (GL1): the assurance level in the token, the gates, and new-device emails."""

import datetime as dt
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api.devices import get_sender
from app.core import config
from app.core.mfa import sensitive_action_needs_mfa
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


def test_sensitive_actions_wait_for_the_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_MFA_ENFORCED", "true")
    monkeypatch.setenv("API_MFA_REQUIRED_FROM", "2026-11-01")
    config.get_settings.cache_clear()
    try:
        assert not sensitive_action_needs_mfa("aal1", dt.date(2026, 10, 31))
        assert sensitive_action_needs_mfa("aal1", dt.date(2026, 11, 1))
        assert not sensitive_action_needs_mfa("aal2", dt.date(2026, 11, 1))
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()


def test_owners_need_a_code_for_sensitive_actions(
    client: TestClient, studio: dict, auth: AuthHeaders, mfa_on: None
) -> None:
    owner_id = client.get("/me", headers=studio["headers"]).json()["id"]
    headers = auth(owner_id, studio["tenant_id"], aal="aal1")
    # Everyday work needs no code ...
    assert client.get("/services", headers=headers).status_code == 200
    # ... settings do.
    refused = client.patch(
        "/tenants/current", json={"cancellation_window_minutes": 60}, headers=headers
    )
    assert refused.status_code == 403 and refused.json()["detail"] == "mfa_required"


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
