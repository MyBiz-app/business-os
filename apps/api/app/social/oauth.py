"""What the OAuth connectors share: the signed state that carries a connection across the
network's consent page, the callback address and small HTTP helpers.

The state names the business, the person and the connector, and expires in ten minutes, so the
callback (which has no sign-in header) knows who agreed without trusting the address."""

from typing import Any
from uuid import UUID

import httpx2

from app.core.config import get_settings
from app.core.signed_links import sign, verify

STATE_SECONDS = 600
TIMEOUT = 20.0


class ProviderUnavailable(RuntimeError):
    """The network answered with an error or could not be reached."""


def callback_url(family: str) -> str:
    return f"{get_settings().api_url.rstrip('/')}/social/callback/{family}"


def make_state(tenant_id: UUID, user_id: UUID | None, provider: str) -> str:
    return sign(f"social|{tenant_id}|{user_id or ''}|{provider}", ttl=STATE_SECONDS)


def read_state(state: str) -> tuple[UUID, UUID | None, str] | None:
    subject = verify(state)
    if subject is None:
        return None
    try:
        kind, tenant, user, provider = subject.split("|")
        if kind != "social":
            return None
        return UUID(tenant), (UUID(user) if user else None), provider
    except ValueError:
        return None


def request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    params: Any = None,
    data: dict[str, Any] | None = None,
    json: Any = None,
    client: httpx2.Client | None = None,
) -> dict[str, Any]:
    """One call to a network. 401 on an authorized call means the access is gone (403 is often a
    missing approval or quota, so it is a plain failure)."""
    from app.social.providers import ReauthNeeded

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with client or httpx2.Client(timeout=TIMEOUT) as http:
            response = http.request(
                method, url, headers=headers, params=params, data=data, json=json
            )
    except httpx2.HTTPError as error:
        raise ProviderUnavailable(type(error).__name__) from error
    if token and response.status_code == 401:
        raise ReauthNeeded("HTTP 401")
    if response.status_code >= 400:
        raise ProviderUnavailable(f"HTTP {response.status_code}")
    return response.json() if response.content else {}
