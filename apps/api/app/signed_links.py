"""Short-lived signed links (a phone opens a file by a plain URL, without the sign-in header).

A link names one thing and expires; the signature (HMAC-SHA256 with a key derived from the
platform's secrets key) proves the API issued it."""

import base64
import hashlib
import hmac
import time

from app.core.config import get_settings
from app.providers.secrets import DEV_KEY, SecretsKeyMissing

TTL_SECONDS = 600


def _key() -> bytes:
    """Derived from API_SECRETS_KEY. The development key is public (it is in this repository),
    so outside local development and tests a missing key fails instead of signing with it."""
    settings = get_settings()
    if settings.secrets_key is not None:
        secret = settings.secrets_key.get_secret_value().encode()
    elif settings.environment in ("local", "test"):
        secret = DEV_KEY
    else:
        raise SecretsKeyMissing("API_SECRETS_KEY is required to sign links")
    return hashlib.sha256(b"signed-links:" + secret).digest()


def sign(subject: str, ttl: int = TTL_SECONDS, now: float | None = None) -> str:
    expires = int((now or time.time()) + ttl)
    payload = f"{subject}.{expires}"
    mac = hmac.new(_key(), payload.encode(), hashlib.sha256).digest()
    token = f"{payload}.{base64.urlsafe_b64encode(mac).decode().rstrip('=')}"
    return base64.urlsafe_b64encode(token.encode()).decode().rstrip("=")


def verify(token: str, now: float | None = None) -> str | None:
    """The subject, or None when the link is forged or expired."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        subject, expires, mac = raw.rsplit(".", 2)
        given = base64.urlsafe_b64decode(mac + "=" * (-len(mac) % 4))
        expired = int(expires) < (now or time.time())
    except ValueError:  # not base64, not text, not our shape (binascii and Unicode errors too)
        return None
    expected = hmac.new(_key(), f"{subject}.{expires}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, given) or expired:
        return None
    return subject
