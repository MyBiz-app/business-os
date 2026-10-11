"""Payments: taking a client's payment through the business's payment provider.

A provider makes a hosted payment page for a checkout (the client pays on the provider's page,
card details never touch MyBiz) and reads the provider's notification (webhook) saying how it
ended. The built-in `simulated` provider has no page: the app's own "pay" button completes the
checkout, marked as simulated on every receipt."""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.providers.registry import register


@dataclass(frozen=True)
class CheckoutRequest:
    """What the client is paying for, in the system's words."""

    checkout_id: str  # our id, sent to the provider and returned in its webhook
    amount: int  # minor units
    currency: str  # ISO 4217
    description: str  # "Monthly membership", "Padel court · Court 1 · 8/10 18:00"
    client_name: str
    client_email: str | None
    success_url: str  # where the provider sends the client after paying
    cancel_url: str
    locale: str = "he"


@dataclass(frozen=True)
class HostedCheckout:
    pay_url: str | None  # None: no page (simulated)
    provider_ref: str | None


@dataclass(frozen=True)
class PaymentEvent:
    """A provider's notification, verified and translated."""

    checkout_id: str
    provider_ref: str
    status: Literal["succeeded", "failed"]
    amount: int
    currency: str
    method: str = "card"


class PaymentProvider(Protocol):
    simulated: bool

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout: ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        """Verifies the notification is the provider's (signature) and translates it.
        Raises WebhookRejected when it isn't."""
        ...

    def refund(self, provider_ref: str, amount: int) -> str:
        """Refunds (part of) a payment; returns the provider's refund reference."""
        ...


class WebhookRejected(ValueError):
    """The notification's signature or content is not valid."""


class PaymentsUnavailable(RuntimeError):
    """The provider refused or could not be reached."""


@register(
    "payments",
    "simulated",
    "Simulated (no real money)",
    builtin=True,
    description="Payments are recorded but no card is charged. For demos and before go-live.",
)
class SimulatedPayments:
    simulated = True

    def __init__(self, settings: dict[str, str]) -> None:
        self.settings = settings

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout:
        return HostedCheckout(pay_url=None, provider_ref=None)

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        raise WebhookRejected("the simulated provider sends no webhooks")

    def refund(self, provider_ref: str, amount: int) -> str:
        return f"simulated-refund-{provider_ref}"
