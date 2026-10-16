"""Identity numbers (Israeli ID, passport, foreign ID) of the people a business works with.

An ID number is sensitive personal data. It is stored only encrypted (the platform secrets key),
next to a keyed hash that finds duplicates inside one business without decrypting anything, and
its last four characters for display. Nothing here is ever sent to the AI."""

import hashlib
import hmac
import re
from typing import Literal
from uuid import UUID

from app.core.config import get_settings
from app.providers import secrets

IdType = Literal["il_id", "passport", "foreign"]
ID_TYPES: tuple[str, ...] = ("il_id", "passport", "foreign")

_HMAC_LABEL = b"mybiz-identity-hmac-v1"
_OTHER_NUMBER = re.compile(r"^[A-Z0-9]{5,20}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")


def check_digit_valid(number: str) -> bool:
    """The check digit shared by Israeli ID numbers and company numbers: up to 9 digits,
    weights 1,2,1,2..., digit sums."""
    if not number.isdigit() or len(number) > 9:
        return False
    total = 0
    for index, digit in enumerate(number.zfill(9)):
        value = int(digit) * (1 + index % 2)
        total += value - 9 if value > 9 else value
    return total % 10 == 0 and int(number) > 0


class InvalidIdentity(ValueError):
    """The number or country does not fit the ID type."""


def normalize(id_type: str, number: str, country: str | None) -> tuple[str, str | None]:
    """The canonical number (and country) to store, or InvalidIdentity."""
    if id_type not in ID_TYPES:
        raise InvalidIdentity("id_type")
    cleaned = re.sub(r"[\s\-]", "", number).upper()
    if id_type == "il_id":
        if not cleaned.isdigit() or not check_digit_valid(cleaned):
            raise InvalidIdentity("number")
        return cleaned.zfill(9), "IL"
    if not _OTHER_NUMBER.match(cleaned):
        raise InvalidIdentity("number")
    code = (country or "").strip().upper()
    if not _COUNTRY.match(code):
        raise InvalidIdentity("country")
    return cleaned, code


def last4(number: str) -> str:
    return number[-4:]


def encrypt_number(number: str) -> bytes:
    return secrets.encrypt({"id": number})


def decrypt_number(blob: bytes) -> str:
    return secrets.decrypt(blob)["id"]


def _hmac_key() -> bytes:
    settings = get_settings()
    if settings.secrets_key is not None:
        base = settings.secrets_key.get_secret_value().encode()
    elif settings.environment in ("local", "test"):
        base = secrets.DEV_KEY
    else:
        raise secrets.SecretsKeyMissing("API_SECRETS_KEY is required to store ID numbers")
    return hmac.new(base, _HMAC_LABEL, hashlib.sha256).digest()


def number_hash(tenant_id: UUID, number: str) -> str:
    """Keyed hash of a canonical number, per business: the same person in two businesses has two
    unrelated hashes."""
    return hmac.new(_hmac_key(), f"{tenant_id}:{number}".encode(), hashlib.sha256).hexdigest()
