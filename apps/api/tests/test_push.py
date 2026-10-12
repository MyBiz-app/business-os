from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Engine, text

from app.messaging.email import LogSender
from app.messaging.push import LogPushSender, PushResult
from app.messaging.roster import notify_roster

TOKEN = "ExponentPushToken[abcdefghijklmnop]"


def seed_published_shift(engine: Engine, with_token: bool, email: str) -> None:
    user, tenant, location = uuid4(), uuid4(), uuid4()
    start = datetime.now(UTC) + timedelta(days=1)
    with engine.begin() as c:
        c.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        c.execute(
            text(
                "INSERT INTO app.users (id, email, full_name, email_roster)"
                " VALUES (:i, :e, 'Dana Levi', true)"
            ),
            {"i": user, "e": email},
        )
        c.execute(
            text(
                "INSERT INTO app.tenants (id, name, vertical, locale, time_zone, currency)"
                " VALUES (:i, 'Biz', 'fitness', 'en', 'Asia/Jerusalem', 'ILS')"
            ),
            {"i": tenant},
        )
        c.execute(
            text(
                "INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'staff')"
            ),
            {"t": tenant, "u": user},
        )
        c.execute(
            text("INSERT INTO app.locations (id, tenant_id, name) VALUES (:i, :t, 'Main')"),
            {"i": location, "t": tenant},
        )
        c.execute(
            text(
                "INSERT INTO app.shifts (tenant_id, location_id, user_id, starts_at, ends_at,"
                " published_at) VALUES (:t, :l, :u, :s, :e, now())"
            ),
            {"t": tenant, "l": location, "u": user, "s": start, "e": start + timedelta(hours=8)},
        )
        if with_token:
            c.execute(
                text(
                    "INSERT INTO app.push_tokens (user_id, token, platform) VALUES (:u, :t, 'ios')"
                ),
                {"u": user, "t": TOKEN},
            )


def test_push_replaces_the_email_when_a_phone_is_registered(engine: Engine) -> None:
    seed_published_shift(engine, with_token=True, email="d@example.com")
    sender, push = LogSender(), LogPushSender()
    with engine.begin() as c:
        counts = notify_roster(c, sender, push=push)
    assert counts == {"sent": 0, "failed": 0, "skipped": 0, "pushed": 1}
    assert sender.sent == [] and push.sent[0][0] == [TOKEN]


def test_email_is_the_fallback_without_a_phone(engine: Engine) -> None:
    seed_published_shift(engine, with_token=False, email="d@example.com")
    sender, push = LogSender(), LogPushSender()
    with engine.begin() as c:
        counts = notify_roster(c, sender, push=push)
    assert counts["sent"] == 1 and counts["pushed"] == 0 and push.sent == []


def test_email_is_the_fallback_when_push_fails_and_dead_tokens_are_forgotten(
    engine: Engine,
) -> None:
    class Dead(LogPushSender):
        def send(self, tokens, title, body):  # type: ignore[no-untyped-def]
            return PushResult(delivered=0, dead=tokens)

    seed_published_shift(engine, with_token=True, email="d@example.com")
    sender = LogSender()
    with engine.begin() as c:
        counts = notify_roster(c, sender, push=Dead())
    assert counts["sent"] == 1 and counts["pushed"] == 0
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM app.push_tokens")).scalar_one() == 0


def test_push_only_works_without_an_email_provider(engine: Engine) -> None:
    seed_published_shift(engine, with_token=True, email="")
    push = LogPushSender()
    with engine.begin() as c:
        assert notify_roster(c, None, push=push)["pushed"] == 1


def test_expo_sender_posts_in_batches_and_reports_dead_tokens(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import io
    import json

    from app.messaging import push

    calls: list[int] = []

    class Reply(io.BytesIO):
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return None

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        sent = json.loads(request.data)
        calls.append(len(sent))
        tickets = [
            {"status": "error", "details": {"error": "DeviceNotRegistered"}}
            if message["to"].endswith("dead]")
            else {"status": "ok"}
            for message in sent
        ]
        return Reply(json.dumps({"data": tickets}).encode())

    monkeypatch.setattr(push.urllib.request, "urlopen", fake_urlopen)
    tokens = [f"ExponentPushToken[{i:03}]" for i in range(150)] + ["ExponentPushToken[dead]"]
    result = push.ExpoPushSender().send(tokens, "Hi", "Body")
    assert calls == [100, 51]
    assert result.delivered == 150 and result.dead == ["ExponentPushToken[dead]"]
