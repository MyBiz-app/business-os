"""Marketing consent: where a change came from, and the opt-out wording of an ad."""

from fastapi import Request

from app.core.config import get_settings
from app.core.rate_limit import client_address
from app.messaging.email import load_messages


def request_origin(request: Request) -> tuple[str, str]:
    """The caller's address and device, kept with a consent change as its source."""
    settings = get_settings()
    token = settings.internal_token.get_secret_value() if settings.internal_token else None
    address = client_address(request, settings.trust_forwarded_for, token)
    return address, request.headers.get("user-agent", "")[:300]


def unsubscribe_url(token: str) -> str:
    return f"{get_settings().api_url}/u/{token}"


def promotional_text(body: str, locale: str, token: str | None) -> str:
    """An ad sent as SMS / WhatsApp: marked as an ad, with a one-tap way to stop them."""
    lang = locale if locale in ("he", "en") else "he"
    messages = load_messages(lang)["broadcast"]
    text = f"{messages['ad']}: {body}"
    if token:
        text += f"\n{messages['unsubscribe']}: {unsubscribe_url(token)}"
    return text
