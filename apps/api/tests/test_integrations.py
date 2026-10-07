"""Swappable providers (decision X13): a business connects its own payments, invoicing and
messaging providers; the built-in ones work with no account. The test providers below stand in
for a real vendor and exercise the same paths one would."""

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.outbox import issue_documents, send_messages
from app.providers.invoicing import InvoiceDocument, IssuedDocument
from app.providers.messaging import OutgoingMessage, SendResult
from app.providers.payments import CheckoutRequest, HostedCheckout, PaymentEvent, WebhookRejected
from app.providers.registry import REGISTRY, SettingField, register
from tests.conftest import AuthHeaders, add_member, make_staff
from tests.test_checkouts import setup
from tests.test_messaging import add_client, with_messaging

SENT: list[OutgoingMessage] = []
ISSUED: list[InvoiceDocument] = []


if ("payments", "testpay") not in REGISTRY.providers:

    @register(
        "payments",
        "testpay",
        "Test pay",
        fields=(
            SettingField("terminal", "Terminal"),
            SettingField("secret", "Secret", secret=True),
        ),
    )
    class FakePay:
        simulated = False

        def __init__(self, settings: dict[str, str]) -> None:
            self.secret = settings["secret"].encode()

        def create_checkout(self, request: CheckoutRequest) -> HostedCheckout:
            ref = f"tp-{request.checkout_id}"
            return HostedCheckout(
                pay_url=f"https://pay.example/{ref}?a={request.amount}", provider_ref=ref
            )

        def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
            expected = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, headers.get("x-signature", "")):
                raise WebhookRejected("bad signature")
            data = json.loads(body)
            return PaymentEvent(
                checkout_id=data["checkout"],
                provider_ref=data["ref"],
                status=data["status"],
                amount=data["amount"],
                currency=data["currency"],
            )

        def refund(self, provider_ref: str, amount: int) -> str:
            return f"refund-{provider_ref}"

    @register(
        "messaging", "testsms", "Test SMS", fields=(SettingField("token", "Token", secret=True),)
    )
    class FakeSms:
        simulated = False

        def __init__(self, settings: dict[str, str]) -> None:
            self.token = settings["token"]

        def send(self, message: OutgoingMessage) -> SendResult:
            if message.to.endswith("0000"):
                raise ConnectionError("provider down")
            SENT.append(message)
            return SendResult(status="sent", provider_ref=f"sms-{len(SENT)}")

    @register(
        "invoicing",
        "testinvoice",
        "Test invoices",
        fields=(SettingField("api_key", "Key", secret=True),),
    )
    class FakeInvoices:
        def __init__(self, settings: dict[str, str]) -> None:
            self.key = settings["api_key"]

        def issue(self, document: InvoiceDocument) -> IssuedDocument:
            ISSUED.append(document)
            return IssuedDocument(
                number=f"INV-{document.receipt_number}",
                url=f"https://invoices.example/{document.receipt_id}.pdf",
                provider_ref=document.receipt_id,
            )


def signed(event: dict, secret: bytes = b"k") -> tuple[bytes, str]:
    """A notification as the stand-in payments provider sends it."""
    raw = json.dumps(event).encode()
    return raw, hmac.new(secret, raw, hashlib.sha256).hexdigest()


def connect(client: TestClient, headers: dict, capability: str, provider: str, **settings):
    return client.put(
        f"/integrations/{capability}",
        json={"provider": provider, "settings": settings},
        headers=headers,
    )


def test_builtin_providers_are_the_default(client: TestClient, studio: dict) -> None:
    listed = client.get("/integrations", headers=studio["headers"])
    assert listed.status_code == 200, listed.text
    by = {i["capability"]: i for i in listed.json()}
    assert by["payments"]["provider"] == "simulated" and by["payments"]["own"] is False
    assert by["invoicing"]["provider"] == "internal"
    assert by["messaging"]["provider"] == "simulated"
    assert "testpay" in [o["name"] for o in by["payments"]["options"]]


def test_connect_switch_and_disconnect(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    missing = connect(client, headers, "payments", "testpay", terminal="123")
    assert missing.status_code == 422
    unknown = connect(client, headers, "payments", "nope")
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_provider"

    connected = connect(client, headers, "payments", "testpay", terminal="123", secret="s3cret")
    assert connected.status_code == 200, connected.text
    body = connected.json()
    assert body["own"] and body["provider"] == "testpay"
    assert body["settings"] == {"terminal": "123"} and body["secrets_set"] == ["secret"]
    assert "s3cret" not in connected.text
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT settings::text || encode(secrets, 'escape') FROM app.tenant_integrations")
        ).scalar_one()
    assert "s3cret" not in stored  # encrypted at rest

    # An empty secret keeps the one already set (changing only the terminal).
    kept = connect(client, headers, "payments", "testpay", terminal="456", secret="")
    assert kept.status_code == 200 and kept.json()["settings"] == {"terminal": "456"}

    # Staff can't see or change integrations.
    staff = uuid4()
    add_member(engine, studio["tenant_id"], staff, "staff")
    assert client.get("/integrations", headers=auth(staff, studio["tenant_id"])).status_code == 403

    back = client.delete("/integrations/payments", headers=headers)
    assert back.json()["provider"] == "simulated" and back.json()["own"] is False


def test_checkout_through_a_payment_provider(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    connect(client, studio["headers"], "payments", "testpay", terminal="1", secret="k")
    _, headers, card = setup(client, auth, studio)
    checkout = client.post(
        "/client/checkouts", json={"plan_id": card["id"]}, headers=headers
    ).json()
    assert checkout["simulated"] is False

    page = client.post(f"/client/checkouts/{checkout['id']}/pay-page", headers=headers)
    assert page.status_code == 200, page.text
    assert page.json()["pay_url"].startswith("https://pay.example/tp-")
    refused = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)
    assert refused.status_code == 404  # only the provider completes it

    url = f"/webhooks/payments/testpay/{studio['tenant_id']}"
    event = {"checkout": checkout["id"], "ref": "tp-1", "status": "succeeded",
             "amount": checkout["amount"], "currency": checkout["currency"]}  # fmt: skip
    raw = json.dumps(event).encode()
    signature = hmac.new(b"k", raw, hashlib.sha256).hexdigest()
    forged = client.post(url, content=raw, headers={"x-signature": "0" * 64})
    assert forged.status_code == 401
    wrong = json.dumps({**event, "amount": 1}).encode()
    mismatch = client.post(
        url,
        content=wrong,
        headers={"x-signature": hmac.new(b"k", wrong, hashlib.sha256).hexdigest()},
    )
    assert mismatch.status_code == 409

    paid = client.post(url, content=raw, headers={"x-signature": signature})
    assert paid.status_code == 204, paid.text
    again = client.post(url, content=raw, headers={"x-signature": signature})
    assert again.status_code == 204  # providers retry: the same notification changes nothing
    done = client.get(f"/client/checkouts/{checkout['id']}", headers=headers).json()
    assert done["status"] == "paid"
    entitlements = client.get("/client/entitlements", headers=headers).json()
    assert [e["name"] for e in entitlements] == [card["name"]]
    receipts = client.get("/client/receipts", headers=headers).json()
    assert len(receipts) == 1 and receipts[0]["simulated"] is False

    other = f"/webhooks/payments/simulated/{studio['tenant_id']}"
    assert client.post(other, content=raw).status_code == 404


def test_messages_go_through_the_business_provider(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    connect(client, headers, "messaging", "testsms", token="t")
    dana = add_client(client, headers, "Dana", "050-1111111")
    down = add_client(client, headers, "Noa", "050-0000000")
    for target in (dana, down):
        sent = client.post(
            "/messages/direct",
            json={"client_id": target, "body": "Hi {first_name}"},
            headers=headers,
        )
        assert sent.status_code in (200, 201), sent.text
    with engine.connect() as connection:
        statuses = (
            connection.execute(
                text("SELECT status FROM app.messages WHERE tenant_id = :t"),
                {"t": studio["tenant_id"]},
            )
            .scalars()
            .all()
        )
    assert statuses == ["queued", "queued"]

    SENT.clear()
    with engine.begin() as connection:
        first = send_messages(connection)
    assert first["sent"] == 1 and first["waiting"] == 1
    assert SENT[0].body == "Hi Dana" and SENT[0].to == "050-1111111"
    for _ in range(5):  # the provider stays down: given up after the attempts
        with engine.begin() as connection:
            send_messages(connection)
    with engine.connect() as connection:
        rows = dict(
            connection.execute(
                text("SELECT to_phone, status FROM app.messages WHERE tenant_id = :t"),
                {"t": studio["tenant_id"]},
            ).all()
        )
    assert rows == {"050-1111111": "sent", "050-0000000": "failed"}


def test_receipts_get_their_document(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    _, headers, card = setup(client, auth, studio)
    checkout = client.post(
        "/client/checkouts", json={"plan_id": card["id"]}, headers=headers
    ).json()
    client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)

    # Without a connection the receipt itself is the document.
    with engine.begin() as connection:
        assert issue_documents(connection)["internal"] >= 1

    connect(client, studio["headers"], "invoicing", "testinvoice", api_key="x")
    second = client.post("/client/checkouts", json={"plan_id": card["id"]}, headers=headers).json()
    client.post(f"/client/checkouts/{second['id']}/simulate-payment", headers=headers)
    ISSUED.clear()
    with engine.begin() as connection:
        issued = issue_documents(connection)
    assert issued["issued"] == 1 and ISSUED[0].total == card["price_amount"]
    with engine.connect() as connection:
        document = connection.execute(
            text("""
                SELECT document_status, document_number, document_url FROM app.receipts
                WHERE tenant_id = :t ORDER BY number DESC LIMIT 1
            """),
            {"t": studio["tenant_id"]},
        ).one()
    assert document.document_status == "issued"
    assert document.document_number == f"INV-{ISSUED[0].receipt_number}"
    assert document.document_url.endswith(".pdf")


@pytest.mark.parametrize("capability", ["payments", "invoicing", "messaging", "email", "ai"])
def test_platform_console_lists_capabilities(
    client: TestClient, capability: str, engine: Engine, auth: AuthHeaders
) -> None:
    admin = uuid4()
    make_staff(engine, admin, "owner", ())
    listed = client.get("/platform/integrations", headers=auth(admin))
    assert listed.status_code == 200, listed.text
    entry = next(c for c in listed.json() if c["capability"] == capability)
    assert entry["options"] and entry["default_provider"]
