"""Encrypting a business's provider secrets (API keys, terminal passwords) at rest.

The key is the platform's `API_SECRETS_KEY` (a Fernet key, kept in the provider secret store).
Local development and tests use a fixed development key; any other environment refuses to
store secrets without a real one."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"mybiz-local-development-only").digest())


class SecretsKeyMissing(RuntimeError):
    """API_SECRETS_KEY is not set outside local development."""


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.secrets_key is not None:
        return Fernet(settings.secrets_key.get_secret_value().encode())
    if settings.environment in ("local", "test"):
        return Fernet(DEV_KEY)
    raise SecretsKeyMissing("API_SECRETS_KEY is required to store provider secrets")


def encrypt(values: dict[str, str]) -> bytes:
    return _fernet().encrypt(json.dumps(values, sort_keys=True).encode())


def decrypt(blob: bytes | None) -> dict[str, str]:
    if not blob:
        return {}
    try:
        return json.loads(_fernet().decrypt(bytes(blob)))
    except InvalidToken as error:  # the key changed: the business connects again
        raise SecretsKeyMissing("stored secrets cannot be read with the current key") from error
