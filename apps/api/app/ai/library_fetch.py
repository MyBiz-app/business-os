"""Reading a web page or file for an agent's library from its link (slice C3a).

The team adds a link to an official source; this reads it so the agent can search its text. Only
https addresses of the public internet are read: the address is resolved first and refused when it
points at a private, loopback or link-local address, and the connection then goes to exactly the
address that was checked (so a name cannot change its answer in between). Redirects are followed
a few times and every hop is checked the same way."""

import http.client
import ipaddress
import socket
import ssl
import urllib.parse

from app.ai.knowledge import MAX_TEXT, UnsupportedFile, extract_text

MAX_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT = 15.0
USER_AGENT = "MyBizLibraryBot/1.0"


class FetchError(Exception):
    """The page could not be read; the message is a short code for the console."""


def _public_address(host: str, port: int) -> str:
    try:
        found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise FetchError("host_not_found") from error
    addresses = {item[4][0] for item in found}
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise FetchError("address_not_allowed")
    return sorted(addresses)[0]


class _Pinned(http.client.HTTPSConnection):
    """An HTTPS connection to one already checked address, with the real name for TLS."""

    def __init__(self, host: str, address: str, port: int) -> None:
        super().__init__(host, port, timeout=TIMEOUT, context=ssl.create_default_context())
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)  # type: ignore[attr-defined]


def _get(url: str) -> tuple[bytes, str, str]:
    """The bytes, the content type and the final address of a page."""
    for _ in range(MAX_REDIRECTS + 1):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise FetchError("https_only")
        port = parts.port or 443
        connection = _Pinned(parts.hostname, _public_address(parts.hostname, port), port)
        try:
            path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
            connection.request(
                "GET",
                path,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,*/*"},
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise FetchError("bad_redirect")
                url = urllib.parse.urljoin(url, location)
                continue
            if response.status != 200:
                raise FetchError(f"http_{response.status}")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise FetchError("file_too_large")
            return data, response.getheader("Content-Type") or "", url
        except (OSError, http.client.HTTPException, ssl.SSLError) as error:
            raise FetchError("unreachable") from error
        finally:
            connection.close()
    raise FetchError("too_many_redirects")


def _filename(content_type: str, url: str) -> str:
    kind = content_type.split(";")[0].strip().lower()
    if kind == "application/pdf":
        return "page.pdf"
    if "wordprocessingml" in kind:
        return "page.docx"
    if kind == "text/plain":
        return "page.txt"
    if kind in ("text/html", "application/xhtml+xml", ""):
        path = urllib.parse.urlsplit(url).path.lower()
        return "page.pdf" if path.endswith(".pdf") else "page.html"
    raise FetchError("unsupported_file")


def fetch_text(url: str) -> str:
    """The text of the page or file at an https address."""
    data, content_type, final = _get(url)
    try:
        return extract_text(_filename(content_type, final), data)[:MAX_TEXT]
    except UnsupportedFile as error:
        raise FetchError(str(error)) from error
