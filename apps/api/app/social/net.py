"""One HTTP call to a network, with failures as our own exceptions (Google and TikTok)."""

from typing import Any

import httpx2

from app.social.providers import NeedsReauth, NetworkError

TIMEOUT = 20.0


def request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    params: Any = None,
    data: dict[str, Any] | None = None,
    json: Any = None,
) -> dict[str, Any]:
    """401 on an authorized call means the access is gone (403 is often a missing approval or
    quota, so it is a plain failure)."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx2.Client(timeout=TIMEOUT) as http:
            response = http.request(
                method, url, headers=headers, params=params, data=data, json=json
            )
    except httpx2.HTTPError as error:
        raise NetworkError(type(error).__name__) from error
    if token and response.status_code == 401:
        raise NeedsReauth("HTTP 401")
    if response.status_code >= 400:
        raise NetworkError(f"HTTP {response.status_code}")
    return response.json() if response.content else {}
