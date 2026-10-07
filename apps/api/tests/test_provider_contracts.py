"""Every registered provider keeps its capability's contract (decision X13).

A new vendor is one class with `@register(...)`; these tests pick it up on their own and check
that it can be built from its declared settings and has what the rest of the system calls. They
need no database and no network."""

from datetime import UTC, datetime

import pytest

from app.providers import choice  # noqa: F401  (imports every provider module)
from app.providers.invoicing import DocumentLine, InvoiceDocument
from app.providers.messaging import OutgoingMessage
from app.providers.payments import CheckoutRequest, WebhookRejected
from app.providers.registry import CAPABILITIES, PER_BUSINESS, REGISTRY, ProviderInfo

# What the system calls on each capability's provider instance.
CONTRACT: dict[str, tuple[str, ...]] = {
    "payments": ("simulated", "create_checkout", "parse_webhook", "refund"),
    "invoicing": ("issue",),
    "messaging": ("simulated", "send"),
    "email": ("send",),
    "ai": ("model", "create"),
    "storage": ("in_database", "put", "get", "delete"),
}
PROVIDERS = sorted(REGISTRY.providers.values(), key=lambda p: (p.capability, p.name))


def dummy_settings(info: ProviderInfo) -> dict[str, str]:
    """A value for every declared setting, the way settings → Integrations would send them."""
    return {f.key: "465" if f.key == "port" else f"test-{f.key}" for f in info.fields}


def test_every_capability_has_a_builtin_provider() -> None:
    assert set(CONTRACT) == set(CAPABILITIES)
    for capability in CAPABILITIES:
        builtins = [p for p in REGISTRY.of(capability) if p.builtin]
        assert builtins, f"{capability} has no provider that works without an account"
        assert all(not any(f.required for f in p.fields) for p in builtins)
    assert set(PER_BUSINESS) <= set(CAPABILITIES)


@pytest.mark.parametrize("info", PROVIDERS, ids=lambda p: f"{p.capability}/{p.name}")
def test_provider_declares_itself_clearly(info: ProviderInfo) -> None:
    assert info.capability in CAPABILITIES
    assert info.name and info.name == info.name.lower() and " " not in info.name
    assert info.label.strip()
    keys = [f.key for f in info.fields]
    assert len(keys) == len(set(keys)), "a setting is declared twice"
    assert all(f.label.strip() for f in info.fields)
    # Anything that looks like a credential must be kept encrypted and never shown again.
    for f in info.fields:
        if any(word in f.key for word in ("key", "secret", "password", "token")):
            assert f.secret, f"{info.capability}/{info.name}: {f.key} should be secret"


@pytest.mark.parametrize("info", PROVIDERS, ids=lambda p: f"{p.capability}/{p.name}")
def test_provider_builds_from_its_settings_and_keeps_the_contract(info: ProviderInfo) -> None:
    instance = info.factory(dummy_settings(info))
    missing = [name for name in CONTRACT[info.capability] if not hasattr(instance, name)]
    assert not missing, f"{info.capability}/{info.name} lacks {missing}"


def test_builtin_providers_behave() -> None:
    payments = REGISTRY.get("payments", "simulated").factory({})
    checkout = payments.create_checkout(
        CheckoutRequest(
            checkout_id="c1",
            amount=5000,
            currency="ILS",
            description="Membership",
            client_name="Dana",
            client_email=None,
            success_url="https://example.com/ok",
            cancel_url="https://example.com/cancel",
        )
    )
    assert payments.simulated and checkout.pay_url is None
    with pytest.raises(WebhookRejected):
        payments.parse_webhook({}, b"{}")

    invoices = REGISTRY.get("invoicing", "internal").factory({})
    issued = invoices.issue(
        InvoiceDocument(
            receipt_id="r1",
            receipt_number=1001,
            issued_at=datetime.now(UTC),
            business_name="Studio",
            client_name="Dana",
            client_email=None,
            lines=(DocumentLine("Membership", 1, 5000),),
            total=5000,
            currency="ILS",
            payment_method="card",
        )
    )
    assert issued.number is None  # MyBiz's own receipt is the document

    messages = REGISTRY.get("messaging", "simulated").factory({})
    sent = messages.send(OutgoingMessage("m1", "whatsapp", "+972500000000", "Hi"))
    assert sent.status == "sent" and sent.provider_ref

    storage = REGISTRY.get("storage", "database").factory({})
    assert storage.in_database and storage.put("k", b"abc", "text/plain").size == 3
