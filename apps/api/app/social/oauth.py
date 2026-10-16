"""The `state` of an OAuth connection: who started it, signed, short-lived.

The network sends the browser back to a public callback with no login, so the state is what
says which business and person the new accounts belong to. It is encrypted with
API_SECRETS_KEY (nobody can read or forge it) and expires after ten minutes."""

import secrets
import time
from uuid import UUID

from app.providers.secrets import decrypt, encrypt

STATE_TTL_SECONDS = 600


def make_state(tenant_id: UUID, user_id: UUID | None, provider: str) -> str:
    return encrypt(
        {
            "t": str(tenant_id),
            "u": str(user_id) if user_id else "",
            "p": provider,
            "exp": str(int(time.time()) + STATE_TTL_SECONDS),
            "n": secrets.token_urlsafe(8),
        }
    ).decode()


def read_state(state: str, provider: str) -> tuple[UUID, UUID | None] | None:
    """The tenant and person of a valid state for `provider`, else None."""
    try:
        data = decrypt(state.encode())
        if data.get("p") != provider or int(data.get("exp", "0")) < time.time():
            return None
        return UUID(data["t"]), (UUID(data["u"]) if data.get("u") else None)
    except Exception:
        return None
