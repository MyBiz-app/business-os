"""Tokens and codes: random, shown once, kept only as a SHA-256 hash (they carry 256 bits, so a
plain hash is enough and the lookup can use an index)."""

import hashlib
import secrets

ACCESS_PREFIX = "mbat_"
REFRESH_PREFIX = "mbrt_"
CODE_PREFIX = "mbac_"
CLIENT_PREFIX = "mbc_"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token(prefix: str) -> tuple[str, str]:
    """A new secret and its hash."""
    raw = prefix + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def new_client_id() -> str:
    return CLIENT_PREFIX + secrets.token_urlsafe(16)
