"""AI replies on WhatsApp (module whatsapp_ai): the AI answers only through its client-facing
tools, offering a slot stores a server-side offer, and only the client's "1" (handled by the
server, not the model) books it, once."""

import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.email import load_all_messages
from app.messaging.whatsapp_ai import answer_inbox
from app.providers.messaging import IncomingMessage, OutgoingMessage, SendResult
from app.providers.payments import WebhookRejected
from app.providers.registry import REGISTRY, SettingField, register
from tests.conftest import local_today
from tests.test_assistant import FakeProvider, calls, says
from tests.test_bookings import new_session
from tests.test_integrations import connect
from tests.test_messaging import add_client

PHONE = "050-1234567"

if ("messaging", "testwa") not in REGISTRY.providers:

    @register(
        "messaging",
        "testwa",
        "Test WhatsApp",
        fields=(SettingField("secret", "Secret", secret=True),),
    )
    class FakeWhatsApp:
        simulated = False

        def __init__(self, settings: dict[str, str]) -> None:
            self.secret = settings["secret"].encode()

        def send(self, message: OutgoingMessage) -> SendResult:
            return SendResult(status="sent", provider_ref=f"wa-{message.message_id}")

        def parse_inbound(self, headers: dict[str, str], body: bytes) -> list[IncomingMessage]:
            expected = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, headers.get("x-signature", "")):
                raise WebhookRejected("bad signature")
            return [IncomingMessage(**m) for m in json.loads(body)["messages"]]


def with_bot(client: TestClient, headers: dict, engine: Engine) -> None:
    modules = {"whatsapp": 1, "ai_basic": 1, "whatsapp_ai": 1}
    response = client.put("/tenants/current/modules", json={"modules": modules}, headers=headers)
    assert response.status_code == 200, response.text
    # Booking themselves, clients follow the client app's rules (a valid plan, a health
    # declaration); this studio asks for neither.
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE app.tenants
                SET requires_health_declaration = false, booking_requires_plan = false
            """)
        )


def receive(engine: Engine, tenant_id: str, body: str, phone: str = "+972501234567") -> bool:
    with engine.begin() as connection:
        return connection.execute(
            text("SELECT app.receive_whatsapp(:t, 'testwa', :ref, :phone, :body)"),
            {"t": tenant_id, "ref": uuid4().hex, "phone": phone, "body": body},
        ).scalar_one()


def run_job(engine: Engine, provider: FakeProvider) -> dict[str, int]:
    with engine.begin() as connection:
        return answer_inbox(connection, provider)


def free_slots_call():
    return calls("free_slots", {"start_date": local_today().isoformat(), "days": 14})


def test_needs_the_module(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    assert client.get("/whatsapp-ai/conversations", headers=headers).status_code == 403
    response = client.post("/whatsapp-ai/try", json={"phone": PHONE, "text": "hi"}, headers=headers)
    assert response.status_code == 403
    # Without the module the inbox takes nothing.
    assert receive(engine, studio["tenant_id"], "hi") is False


def test_a_client_books_a_slot_by_replying_1(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_bot(client, headers, engine)
    dana = add_client(client, headers, "Dana", PHONE)
    session_id = new_session(client, studio, capacity=2, on=local_today() + timedelta(days=3))

    assert receive(engine, studio["tenant_id"], "Any Pilates this week?") is True
    provider = FakeProvider([
        free_slots_call(),
        calls("offer_booking", {"session_id": session_id}),
        says("There's Pilates at 18:00."),
    ])  # fmt: skip
    assert run_job(engine, provider) == {"answered": 1, "skipped": 0, "failed": 0, "waiting": 0}

    # The model saw only the client-facing tools, and the free slot came from the schedule.
    assert {t["name"] for t in provider.calls[0]["tools"]} == {
        "business_info",
        "free_slots",
        "my_bookings",
        "offer_booking",
    }
    slots = json.loads(provider.calls[1]["messages"][-1]["content"][0]["content"])["free"]
    assert [s["session_id"] for s in slots] == [session_id]
    with engine.connect() as connection:
        sent = connection.execute(
            text("SELECT body, status, client_id::text FROM app.messages")
        ).one()
        offer = connection.execute(text("SELECT status FROM app.whatsapp_offers")).scalar_one()
        bookings = connection.execute(text("SELECT count(*) FROM app.bookings")).scalar_one()
    assert sent.client_id == dana and sent.status == "sent"  # the simulated provider
    assert sent.body.startswith("There's Pilates at 18:00.\n\n")
    assert "1" in sent.body.split("\n\n")[1]  # the server's own line asks for 1
    assert offer == "pending" and bookings == 0  # the AI booked nothing

    # "1" is answered by the server: no model call, booked once, audited as the AI.
    receive(engine, studio["tenant_id"], " 1 ")
    idle = FakeProvider([])
    assert run_job(engine, idle)["answered"] == 1 and idle.calls == []
    with engine.connect() as connection:
        booking = connection.execute(
            text("SELECT client_id::text, session_id::text, status FROM app.bookings")
        ).one()
        offer = connection.execute(text("SELECT status FROM app.whatsapp_offers")).scalar_one()
        audit = connection.execute(
            text("SELECT actor_type, action FROM app.audit_log WHERE entity_type = 'booking'")
        ).one()
        replies = (
            connection.execute(text("SELECT body FROM app.messages ORDER BY created_at"))
            .scalars()
            .all()
        )
    assert (booking.client_id, booking.session_id, booking.status) == (dana, session_id, "booked")
    assert offer == "accepted"
    assert (audit.actor_type, audit.action) == ("ai", "whatsapp_ai.book_session")
    assert len(replies) == 2

    # A second "1" has no offer left: it goes to the model like any message.
    receive(engine, studio["tenant_id"], "1")
    again = FakeProvider([says("You're all set already.")])
    run_job(engine, again)
    assert len(again.calls) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM app.bookings")).scalar_one() == 1

    # The business sees the conversation, with the offer.
    listed = client.get("/whatsapp-ai/conversations", headers=headers).json()
    assert [c["client_id"] for c in listed] == [dana]
    detail = client.get(f"/whatsapp-ai/conversations/{listed[0]['id']}", headers=headers).json()
    assert [t["role"] for t in detail["turns"]] == ["client", "ai", "client", "ai", "client", "ai"]
    assert detail["turns"][0]["text"] == "Any Pilates this week?"
    assert detail["turns"][1]["text"] == sent.body
    assert [o["status"] for o in detail["offers"]] == ["accepted"]


def test_declined_expired_and_unknown_numbers(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_bot(client, headers, engine)
    add_client(client, headers, "Dana", PHONE)
    session_id = new_session(client, studio, on=local_today() + timedelta(days=3))

    def offer() -> None:
        receive(engine, studio["tenant_id"], "Book me")
        run_job(engine, FakeProvider([calls("offer_booking", {"session_id": session_id}),
                                      says("Sure.")]))  # fmt: skip

    offer()
    receive(engine, studio["tenant_id"], "0")
    run_job(engine, FakeProvider([]))
    offer()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.whatsapp_offers SET expires_at = now() - interval '1 minute'"
                 " WHERE status = 'pending'")
        )  # fmt: skip
    receive(engine, studio["tenant_id"], "1")
    run_job(engine, FakeProvider([]))
    # A number that is no client's gets no answer (and no model call).
    receive(engine, studio["tenant_id"], "hello", phone="052-9999999")
    assert run_job(engine, FakeProvider([]))["skipped"] == 1

    with engine.connect() as connection:
        offers = (
            connection.execute(text("SELECT status FROM app.whatsapp_offers ORDER BY created_at"))
            .scalars()
            .all()
        )
        assert connection.execute(text("SELECT count(*) FROM app.bookings")).scalar_one() == 0
        notes = (
            connection.execute(text("SELECT note FROM app.whatsapp_inbox WHERE status = 'skipped'"))
            .scalars()
            .all()
        )
    assert offers == ["declined", "expired"]
    assert notes == ["unknown_number"]


def test_the_ai_cannot_offer_what_is_not_bookable(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_bot(client, headers, engine)
    add_client(client, headers, "Dana", PHONE)
    past = new_session(client, studio, on=local_today() - timedelta(days=2))
    provider = FakeProvider([
        calls("offer_booking", {"session_id": past}),
        calls("offer_booking", {"session_id": "not-an-id"}),
        says("Sorry, that one is not available."),
    ])  # fmt: skip
    response = client.post(
        "/whatsapp-ai/try", json={"phone": PHONE, "text": "book the last one"}, headers=headers
    )
    assert response.status_code == 503  # no AI key in tests until a provider is installed
    from app.ai.gateway import get_provider

    client.app.dependency_overrides[get_provider] = lambda: provider  # type: ignore[attr-defined]
    try:
        response = client.post(
            "/whatsapp-ai/try", json={"phone": PHONE, "text": "book the last one"}, headers=headers
        )
    finally:
        client.app.dependency_overrides.pop(get_provider)  # type: ignore[attr-defined]
    assert response.status_code == 200, response.text
    assert response.json() == {"reply": "Sorry, that one is not available.", "offer_id": None}
    errors = [
        json.loads(call["messages"][-1]["content"][0]["content"]) for call in provider.calls[1:]
    ]
    assert all("error" in e for e in errors)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM app.whatsapp_offers")).scalar_one() == 0
        )


def test_trying_the_bot_books_nothing(client: TestClient, studio: dict, engine: Engine) -> None:
    from app.ai.gateway import get_provider

    headers = studio["headers"]
    with_bot(client, headers, engine)
    add_client(client, headers, "Dana", PHONE)
    session_id = new_session(client, studio, on=local_today() + timedelta(days=3))
    provider = FakeProvider([calls("offer_booking", {"session_id": session_id}), says("Yes!")])
    client.app.dependency_overrides[get_provider] = lambda: provider  # type: ignore[attr-defined]
    try:
        first = client.post(
            "/whatsapp-ai/try", json={"phone": PHONE, "text": "book me"}, headers=headers
        )
        accepted = client.post(
            "/whatsapp-ai/try", json={"phone": PHONE, "text": "1"}, headers=headers
        )
        stranger = client.post(
            "/whatsapp-ai/try", json={"phone": "052-9999999", "text": "hi"}, headers=headers
        )
    finally:
        client.app.dependency_overrides.pop(get_provider)  # type: ignore[attr-defined]
    assert first.status_code == 200 and first.json()["offer_id"] is not None
    assert accepted.status_code == 200, accepted.text
    assert stranger.status_code == 422 and stranger.json()["detail"] == "unknown_client"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM app.bookings")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM app.messages")).scalar_one() == 0
        result = connection.execute(text("SELECT result FROM app.whatsapp_offers")).scalar_one()
    assert result == {"status": "booked", "test": True}
    # Tries stay out of the business's conversations, and can be reset.
    assert client.get("/whatsapp-ai/conversations", headers=headers).json() == []
    assert client.delete("/whatsapp-ai/try", headers=headers).status_code == 204
    with engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM app.whatsapp_conversations"))
        assert count.scalar_one() == 0


def test_webhook_files_verified_messages_only(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    tenant_id = studio["tenant_id"]
    url = f"/webhooks/whatsapp/testwa/{tenant_id}"
    raw = json.dumps(
        {"messages": [{"provider_ref": "m1", "from_phone": PHONE, "body": "hi"}]}
    ).encode()
    signature = hmac.new(b"k", raw, hashlib.sha256).hexdigest()

    # Closed while the business uses the simulated provider.
    assert client.post(url, content=raw, headers={"x-signature": signature}).status_code == 404
    with_bot(client, headers, engine)
    assert connect(client, headers, "messaging", "testwa", secret="k").status_code == 200
    assert client.post(url, content=raw, headers={"x-signature": "bad"}).status_code == 401
    for _ in range(2):  # the provider retries: filed once
        assert client.post(url, content=raw, headers={"x-signature": signature}).status_code == 204
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT from_phone, body FROM app.whatsapp_inbox")).all()
    assert [(r.from_phone, r.body) for r in rows] == [(PHONE, "hi")]


def test_erasing_a_client_removes_their_chats(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_bot(client, headers, engine)
    dana = add_client(client, headers, "Dana", PHONE)
    receive(engine, studio["tenant_id"], "hello")
    run_job(engine, FakeProvider([says("Hi Dana!")]))

    exported = client.get(f"/clients/{dana}/export", headers=headers).json()
    assert len(exported["whatsapp_ai_conversations"]) == 1
    erased = client.post(f"/clients/{dana}/erase", json={"confirm": True}, headers=headers)
    assert erased.status_code == 200, erased.text
    with engine.connect() as connection:
        for table in ("whatsapp_conversations", "whatsapp_inbox"):
            count = connection.execute(text(f"SELECT count(*) FROM app.{table}")).scalar_one()
            assert count == 0, table


def test_an_accepted_offer_still_follows_the_booking_rules(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_bot(client, headers, engine)
    add_client(client, headers, "Dana", PHONE)
    session_id = new_session(client, studio, on=local_today() + timedelta(days=3))
    receive(engine, studio["tenant_id"], "Book me")
    run_job(engine, FakeProvider([calls("offer_booking", {"session_id": session_id}), says("Ok")]))
    # Since the offer, the business started asking for a valid plan; Dana has none.
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.tenants SET booking_requires_plan = true"))
    receive(engine, studio["tenant_id"], "1")
    run_job(engine, FakeProvider([]))
    with engine.connect() as connection:
        offer = connection.execute(text("SELECT status, result FROM app.whatsapp_offers")).one()
        last = connection.execute(
            text("SELECT body FROM app.messages ORDER BY created_at DESC LIMIT 1")
        ).scalar_one()
        assert connection.execute(text("SELECT count(*) FROM app.bookings")).scalar_one() == 0
    assert (offer.status, offer.result) == ("failed", {"error": "no_valid_plan"})
    assert last == load_all_messages("he")["whatsappAi"]["failed"]  # the business's language
