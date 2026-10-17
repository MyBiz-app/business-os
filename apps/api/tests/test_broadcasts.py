from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.signed_links import sign
from app.messaging.announcements import send_announcements
from app.messaging.email import LogSender
from app.messaging.push import LogPushSender
from tests.conftest import AuthHeaders, make_staff

TEXTS = {
    "he": {"subject": "פיצ'ר חדש", "body": "בדקו את היומן החדש", "cta_url": "https://mybiz.test/x"},
    "en": {"subject": "New feature", "body": "Try the new calendar", "cta_label": "Open"},
}


def console(engine: Engine, level: str = "owner", permissions: tuple[str, ...] = ()):
    user = uuid4()
    return user, make_staff(engine, user, level, permissions)


def sql(engine: Engine, statement: str, **params: object) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement), params)


def compose(kind: str = "service", channels=("email",), groups=("owners",), **audience) -> dict:
    return {
        "kind": kind,
        "channels": list(channels),
        "audience": {"groups": list(groups), **audience},
        "content": TEXTS,
    }


def run(engine: Engine, sender=None, push=None) -> dict[str, int]:
    with engine.begin() as connection:
        return send_announcements(connection, sender, push)


def test_only_the_broadcast_permission_opens_the_center(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    allowed, _ = console(engine, "employee", ("broadcasts.manage",))
    plain, _ = console(engine, "employee", ("inbox.manage",))
    assert client.get("/platform/broadcasts", headers=auth(owner)).status_code == 200
    assert client.get("/platform/broadcasts", headers=auth(allowed)).status_code == 200
    assert client.get("/platform/broadcasts", headers=auth(plain)).status_code == 403
    # A business owner is not on the team.
    assert client.get("/platform/broadcasts", headers=studio["headers"]).status_code == 403
    assert (
        client.post("/platform/broadcasts", json=compose(), headers=studio["headers"]).status_code
        == 403
    )


def test_a_person_in_several_groups_is_counted_once(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, owner_email = console(engine)
    # The studio's owner is also on the MyBiz team (same email), and the coach is staff.
    sql(engine, "UPDATE app.users SET email = :e WHERE id = :u", e=owner_email, u=studio["owner"])
    sql(engine, "UPDATE app.users SET email = 'coach@example.com' WHERE id = :u", u=studio["coach"])
    headers = auth(owner)

    both = client.post(
        "/platform/broadcasts/preview",
        json={"kind": "service", "audience": {"groups": ["team", "owners", "staff"]}},
        headers=headers,
    ).json()
    # team: the console member (= the studio owner) and the primary owner; staff: the coach.
    assert both["total"] == 3
    assert both["by_group"] == {"owners": 1, "staff": 1, "team": 2}
    assert both["email"] == 3 and both["popup"] == 2


def test_marketing_reaches_only_those_who_agreed(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    sql(engine, "UPDATE app.users SET email = 'owner@example.com' WHERE id = :u", u=studio["owner"])
    audience = {"groups": ["owners"]}
    headers = auth(owner)

    def total(kind: str) -> int:
        return client.post(
            "/platform/broadcasts/preview",
            json={"kind": kind, "audience": audience},
            headers=headers,
        ).json()["total"]

    assert total("service") == 1 and total("marketing") == 0
    # The business owner agrees through their own account.
    assert (
        client.put(
            "/me/marketing-consent", json={"consent": True}, headers=studio["headers"]
        ).status_code
        == 204
    )
    assert total("marketing") == 1
    assert client.get("/me", headers=studio["headers"]).json()["marketing_consent"] is True
    client.put("/me/marketing-consent", json={"consent": False}, headers=studio["headers"])
    assert total("marketing") == 0
    assert client.get("/me", headers=studio["headers"]).json()["marketing_consent"] is False


def test_filters_narrow_the_businesses(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    headers = auth(owner)

    def total(**audience: object) -> int:
        return client.post(
            "/platform/broadcasts/preview",
            json={"kind": "service", "audience": {"groups": ["owners"], **audience}},
            headers=headers,
        ).json()["total"]

    assert total() == 1
    assert total(verticals=["fitness"]) == 1 and total(verticals=["pets"]) == 0
    assert total(locales=["he"]) == 1 and total(locales=["en"]) == 0
    assert total(business_ids=[str(studio["tenant_id"])]) == 1
    assert total(business_ids=[str(uuid4())]) == 0
    assert total(status="trial") == 1 and total(status="active") == 0


def test_a_service_message_goes_out_on_every_channel(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    sql(
        engine,
        "UPDATE app.users SET email = 'owner@example.com', locale = 'en' WHERE id = :u",
        u=studio["owner"],
    )
    sql(
        engine,
        "INSERT INTO app.push_tokens (user_id, token, platform) VALUES (:u, :t, 'ios')",
        u=studio["owner"],
        t="ExponentPushToken[abcdefghijklmnop]",
    )
    client_row = client.post(
        "/clients",
        json={"first_name": "Dana", "email": "dana@example.com", "phone": "+972501234567"},
        headers=studio["headers"],
    ).json()
    headers = auth(owner)

    created = client.post(
        "/platform/broadcasts",
        json=compose(channels=("email", "push", "popup", "whatsapp"), groups=("owners", "clients")),
        headers=headers,
    )
    assert created.status_code == 201
    announcement = created.json()
    assert announcement["status"] == "draft"
    scheduled = client.post(
        f"/platform/broadcasts/{announcement['id']}/schedule", json={}, headers=headers
    )
    assert scheduled.json()["status"] == "scheduled"

    mail, push = LogSender(), LogPushSender()
    counts = run(engine, mail, push)
    assert counts["started"] == 1 and counts["finished"] == 1 and counts["failed"] == 0

    by_to = {m.to: m for m in mail.sent}
    assert set(by_to) == {"owner@example.com", "dana@example.com"}
    assert by_to["owner@example.com"].subject == "New feature"  # the owner reads English
    assert by_to["dana@example.com"].subject == "פיצ'ר חדש"  # the business works in Hebrew
    assert "Ad" not in by_to["owner@example.com"].subject
    assert len(push.sent) == 1 and push.sent[0][1] == "New feature"
    with engine.connect() as connection:
        queued = connection.execute(
            text("SELECT to_phone, channel, status FROM app.messages WHERE client_id = :c"),
            {"c": client_row["id"]},
        ).all()
    assert queued == [("+972501234567", "whatsapp", "queued")]

    # The pop-up waits for the owner's next visit, once dismissed it is gone.
    popups = client.get("/me/announcements", headers=studio["headers"]).json()
    assert [p["texts"]["subject"] for p in popups] == ["New feature"]
    popup_id = popups[0]["id"]
    assert (
        client.post(f"/me/announcements/{popup_id}/viewed", headers=studio["headers"]).status_code
        == 204
    )
    client.post(f"/me/announcements/{popup_id}/clicked", headers=studio["headers"])
    client.post(f"/me/announcements/{popup_id}/dismissed", headers=studio["headers"])
    assert client.get("/me/announcements", headers=studio["headers"]).json() == []
    # Somebody else never sees it, and cannot react to it.
    stranger = auth(uuid4())
    assert client.get("/me/announcements", headers=stranger).json() == []
    assert client.post(f"/me/announcements/{popup_id}/viewed", headers=stranger).status_code == 404

    done = client.get(f"/platform/broadcasts/{announcement['id']}", headers=headers).json()
    assert done["status"] == "sent" and done["recipient_count"] == 2
    assert done["stats"]["sent_by_channel"] == {"email": 2, "push": 1, "popup": 1, "whatsapp": 1}
    assert done["stats"]["viewed"] == 1 and done["stats"]["clicked"] == 1
    # Running the job again sends nothing twice.
    again = run(engine, mail, push)
    assert again["started"] == 0 and len(mail.sent) == 2

    # A sent message can no longer be changed.
    edit = client.put(f"/platform/broadcasts/{announcement['id']}", json=compose(), headers=headers)
    assert edit.status_code == 409


def test_a_marketing_email_says_ad_and_can_be_opted_out_of(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    sql(engine, "UPDATE app.users SET email = 'owner@example.com' WHERE id = :u", u=studio["owner"])
    client.put("/me/marketing-consent", json={"consent": True}, headers=studio["headers"])
    headers = auth(owner)
    created = client.post("/platform/broadcasts", json=compose("marketing"), headers=headers).json()
    client.post(f"/platform/broadcasts/{created['id']}/schedule", json={}, headers=headers)

    mail = LogSender()
    run(engine, mail)
    assert len(mail.sent) == 1
    email = mail.sent[0]
    assert email.subject == "פרסומת: פיצ'ר חדש"
    link = next(w for w in email.text.split() if "/public/announcements/unsubscribe" in w)
    assert link.startswith("http://localhost:8000/public/announcements/unsubscribe?t=")
    assert f'href="{link}"' in email.html  # a clickable opt-out in the designed version too
    assert 'href="https://mybiz.test/x"' in email.html  # the button

    opted_out = client.get(link.replace("http://localhost:8000", ""))
    assert opted_out.status_code == 200
    with engine.connect() as connection:
        consent = connection.execute(
            text("SELECT marketing_consent_at FROM app.users WHERE id = :u"),
            {"u": studio["owner"]},
        ).scalar_one()
        unsubscribed = connection.execute(
            text(
                "SELECT count(*) FROM app.announcement_deliveries WHERE unsubscribed_at IS NOT NULL"
            )
        ).scalar_one()
    assert consent is None and unsubscribed == 1
    stats = client.get(f"/platform/broadcasts/{created['id']}", headers=headers).json()["stats"]
    assert stats["unsubscribed"] == 1

    # A forged or expired link does nothing.
    assert client.get("/public/announcements/unsubscribe?t=forged").status_code == 400
    expired = sign(f"unsub|owner@example.com|{uuid4()}", ttl=-10)
    assert client.get(f"/public/announcements/unsubscribe?t={expired}").status_code == 400


def test_a_message_needs_words_and_an_audience_before_it_is_scheduled(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner, _ = console(engine)
    headers = auth(owner)
    empty = client.post(
        "/platform/broadcasts", json=compose(groups=()) | {"content": {}}, headers=headers
    ).json()
    no_audience = client.post(
        f"/platform/broadcasts/{empty['id']}/schedule", json={}, headers=headers
    )
    assert no_audience.status_code == 422 and no_audience.json()["detail"] == "audience_required"
    client.put(
        f"/platform/broadcasts/{empty['id']}",
        json=compose(groups=("team",)) | {"content": {}},
        headers=headers,
    )
    no_words = client.post(f"/platform/broadcasts/{empty['id']}/schedule", json={}, headers=headers)
    assert no_words.status_code == 422 and no_words.json()["detail"] == "content_required"

    bad_link = compose() | {
        "content": {"he": {"subject": "x", "body": "y", "cta_url": "javascript:1"}}
    }
    assert client.post("/platform/broadcasts", json=bad_link, headers=headers).status_code == 422


def test_a_scheduled_message_waits_for_its_time_and_can_be_cancelled(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner, _ = console(engine)
    headers = auth(owner)
    later = client.post(
        "/platform/broadcasts", json=compose(groups=("team",)), headers=headers
    ).json()
    client.post(
        f"/platform/broadcasts/{later['id']}/schedule",
        json={"scheduled_at": "2999-01-01T00:00:00Z"},
        headers=headers,
    )
    mail = LogSender()
    assert run(engine, mail)["started"] == 0 and mail.sent == []

    cancelled = client.post(f"/platform/broadcasts/{later['id']}/cancel", headers=headers).json()
    assert cancelled["status"] == "cancelled"
    assert client.delete(f"/platform/broadcasts/{later['id']}", headers=headers).status_code == 204
    assert client.get(f"/platform/broadcasts/{later['id']}", headers=headers).status_code == 404
    assert client.get(f"/platform/broadcasts/{UUID(int=1)}", headers=headers).status_code == 404


def test_one_failed_delivery_does_not_stop_the_others(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    owner, _ = console(engine)
    sql(engine, "UPDATE app.users SET email = 'owner@example.com' WHERE id = :u", u=studio["owner"])
    headers = auth(owner)
    created = client.post(
        "/platform/broadcasts", json=compose(groups=("owners", "team")), headers=headers
    ).json()
    client.post(f"/platform/broadcasts/{created['id']}/schedule", json={}, headers=headers)

    class Flaky(LogSender):
        def send(self, email) -> None:
            if email.to == "owner@example.com":
                raise RuntimeError("provider down")
            super().send(email)

    mail = Flaky()
    counts = run(engine, mail)
    assert counts["failed"] >= 1 and len(mail.sent) >= 1
    stats = client.get(f"/platform/broadcasts/{created['id']}", headers=headers).json()
    assert stats["status"] == "sending"  # the failed one is tried again on the next run
    run(engine, mail)
    run(engine, mail)
    final = client.get(f"/platform/broadcasts/{created['id']}", headers=headers).json()
    assert final["status"] == "sent" and final["stats"]["failed"] == 1


def test_a_test_send_goes_only_to_me(
    client: TestClient, engine: Engine, auth: AuthHeaders, monkeypatch
) -> None:
    owner, owner_email = console(engine)
    headers = auth(owner)
    created = client.post("/platform/broadcasts", json=compose(), headers=headers).json()
    mail = LogSender()
    monkeypatch.setattr("app.api.broadcasts.sender_from_settings", lambda: mail)
    result = client.post(f"/platform/broadcasts/{created['id']}/test", headers=headers).json()
    assert result == {"sent_to": owner_email, "email": True}
    assert [m.to for m in mail.sent] == [owner_email]
    monkeypatch.setattr("app.api.broadcasts.sender_from_settings", lambda: None)
    nothing = client.post(f"/platform/broadcasts/{created['id']}/test", headers=headers).json()
    assert nothing["email"] is False
