"""Encrypting a business's provider secrets (API keys, terminal passwords) at rest.

The key is the platform's `API_SECRETS_KEY` (a Fernet key, kept in the provider secret store).
To rotate it, `API_SECRETS_KEYS` lists several keys, newest first: the first encrypts and every
one decrypts (see docs/runbooks/key-rotation.md). Local development and tests use a fixed
development key; any other environment refuses to store secrets without a real one."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings

DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"mybiz-local-development-only").digest())


class SecretsKeyMissing(RuntimeError):
    """API_SECRETS_KEY is not set outside local development."""


def secret_keys() -> list[str]:
    """The platform's keys, newest first. Outside local development and tests, none is an error."""
    settings = get_settings()
    keys = settings.secret_keys()
    if keys:
        return keys
    if settings.environment in ("local", "test"):
        return [DEV_KEY.decode()]
    raise SecretsKeyMissing("API_SECRETS_KEY is required to store provider secrets")


def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(key.encode()) for key in secret_keys()])


def is_current(blob: bytes) -> bool:
    """True when the newest key already encrypts `blob` (so rotating it again changes nothing)."""
    try:
        Fernet(secret_keys()[0].encode()).decrypt(bytes(blob))
    except InvalidToken:
        return False
    return True


def rotate(blob: bytes) -> bytes:
    """`blob` encrypted again with the newest key (it must open with one of the keys)."""
    try:
        return _fernet().rotate(bytes(blob))
    except InvalidToken as error:
        raise SecretsKeyMissing("a stored value cannot be read with any current key") from error


def encrypt(values: dict[str, str]) -> bytes:
    return _fernet().encrypt(json.dumps(values, sort_keys=True).encode())


def decrypt(blob: bytes | None) -> dict[str, str]:
    if not blob:
        return {}
    try:
        return json.loads(_fernet().decrypt(bytes(blob)))
    except InvalidToken as error:  # the key changed: the business connects again
        raise SecretsKeyMissing("stored secrets cannot be read with the current key") from error


def encrypt_bytes(content: bytes) -> bytes:
    """Seals a file's bytes (payslips, employee papers) before they are stored."""
    return _fernet().encrypt(content)


def decrypt_bytes(blob: bytes) -> bytes:
    try:
        return _fernet().decrypt(bytes(blob))
    except InvalidToken as error:
        raise SecretsKeyMissing("a stored file cannot be read with the current key") from error
