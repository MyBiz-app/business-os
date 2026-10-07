"""Messaging: WhatsApp and SMS messages to clients, sent through the business's provider.

Messages wait in an outbox (`app.messages`, status `queued`); the send-messages job hands each
to the provider and records its id and outcome. The built-in `simulated` provider marks them
sent without sending anything."""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.providers.registry import register

Channel = Literal["whatsapp", "sms"]


@dataclass(frozen=True)
class OutgoingMessage:
    message_id: str  # our id
    channel: Channel
    to: str  # the client's phone number as entered
    body: str


@dataclass(frozen=True)
class SendResult:
    status: Literal["sent", "failed"]
    provider_ref: str | None = None
    error: str | None = None


class MessageProvider(Protocol):
    simulated: bool

    def send(self, message: OutgoingMessage) -> SendResult: ...


@register(
    "messaging",
    "simulated",
    "Simulated (nothing is sent)",
    builtin=True,
    description="Messages are recorded as sent but no WhatsApp or SMS goes out.",
)
class SimulatedMessages:
    simulated = True

    def __init__(self, settings: dict[str, str]) -> None:
        self.settings = settings

    def send(self, message: OutgoingMessage) -> SendResult:
        return SendResult(status="sent", provider_ref=f"simulated-{message.message_id}")
