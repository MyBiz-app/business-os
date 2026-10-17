"""A business's or branch's website address: one place that decides what a valid URL is."""

import re
from urllib.parse import urlsplit

MAX_LENGTH = 300
_HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9¡-￿]([a-z0-9¡-￿-]{0,61}[a-z0-9¡-￿])?\.)+[a-z¡-￿]{2,63}$")


def normalize_website(value: str | None) -> str | None:
    """The address as stored: https:// added when people leave it out, scheme and host in lower
    case. An empty value clears it. Raises ValueError for anything that is not a web address
    (other schemes such as javascript:, no host, spaces, a login in the address)."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) > MAX_LENGTH or re.search(r"\s", raw):
        raise ValueError("invalid website")
    if "://" not in raw:
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.IGNORECASE):  # mailto:, javascript:, ...
            raise ValueError("invalid website")
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if parts.scheme.lower() not in ("http", "https") or parts.username or parts.password:
        raise ValueError("invalid website")
    if not _HOST.match(host):
        raise ValueError("invalid website")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("invalid website") from error
    netloc = host if port is None else f"{host}:{port}"
    path = parts.path if parts.path != "/" else ""
    return parts._replace(scheme=parts.scheme.lower(), netloc=netloc, path=path).geturl()
