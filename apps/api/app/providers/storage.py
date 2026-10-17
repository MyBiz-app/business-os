"""Storage: files the system keeps (documents). The built-in `database` provider keeps the
bytes in Postgres next to what they belong to, which is fine for a demo; `supabase` keeps them
in a private Supabase Storage bucket (an object store) under a key that starts with the
business (`tenants/<tenant id>/…`), and hands out short-lived signed links to open them.

Logos, covers and avatars stay in the database: one small, capped image per business or
person (decision T80)."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from app.providers.registry import SettingField, register


@dataclass(frozen=True)
class StoredFile:
    key: str
    content_type: str
    size: int


class StorageProvider(Protocol):
    in_database: bool

    def put(self, key: str, content: bytes, content_type: str) -> StoredFile: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def signed_url(self, key: str, seconds: int) -> str | None:
        """A link that opens the file without signing in, or None when the provider has none
        (the API then serves the bytes itself)."""
        ...


def tenant_key(tenant_id: object, *parts: object) -> str:
    """Every key starts with its business, so a business's files can be found (and removed)
    together and two businesses never share a key."""
    return "/".join(["tenants", str(tenant_id), *(str(p) for p in parts)])


@register(
    "storage",
    "database",
    "In the database",
    builtin=True,
    description="Files are kept in the database next to what they belong to.",
)
class DatabaseStorage:
    """Marker provider: callers keep the bytes in their own table (as logos already do)."""

    in_database = True

    def __init__(self, settings: dict[str, str]) -> None:
        self.settings = settings

    def put(self, key: str, content: bytes, content_type: str) -> StoredFile:
        return StoredFile(key=key, content_type=content_type, size=len(content))

    def get(self, key: str) -> bytes:
        raise LookupError("database storage is read by its owner table")

    def delete(self, key: str) -> None:
        return None

    def signed_url(self, key: str, seconds: int) -> str | None:
        return None


class StorageError(RuntimeError):
    """The object store refused or failed a request."""


@register(
    "storage",
    "supabase",
    "Supabase Storage",
    fields=(
        SettingField("url", "Project URL (https://<project>.supabase.co)"),
        SettingField("service_key", "Secret (service role) key", secret=True),
        SettingField("bucket", "Bucket", required=False),
    ),
    description="Files are kept in a private Supabase Storage bucket.",
)
class SupabaseStorage:
    """Supabase Storage's HTTP API (https://supabase.com/docs/reference/api). The bucket is
    private: every read goes through the API's checks or a signed link that expires."""

    in_database = False
    timeout = 30

    def __init__(self, settings: dict[str, str]) -> None:
        if not settings["url"].startswith(("http://", "https://")):
            raise ValueError("storage url must be http or https")
        self.base = settings["url"].rstrip("/") + "/storage/v1"
        self.key = settings["service_key"]
        self.bucket = settings.get("bucket") or "files"

    def _path(self, key: str) -> str:
        return f"{quote(self.bucket, safe='')}/{quote(key, safe='/')}"

    def _request(
        self, method: str, path: str, body: bytes | None = None, content_type: str | None = None
    ) -> bytes:
        headers = {"Authorization": f"Bearer {self.key}", "apikey": self.key}
        if content_type:
            headers["Content-Type"] = content_type
        if method == "POST" and path.startswith("object/") and not path.startswith("object/sign"):
            headers["x-upsert"] = "true"
        # The scheme is checked in __init__.
        request = urllib.request.Request(  # noqa: S310
            f"{self.base}/{path}", data=body, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in (400, 404) and method == "GET":
                raise LookupError(path) from error
            raise StorageError(f"{method} {path}: {error.code}") from error

    def put(self, key: str, content: bytes, content_type: str) -> StoredFile:
        self._request("POST", f"object/{self._path(key)}", content, content_type)
        return StoredFile(key=key, content_type=content_type, size=len(content))

    def get(self, key: str) -> bytes:
        return self._request("GET", f"object/authenticated/{self._path(key)}")

    def delete(self, key: str) -> None:
        body = json.dumps({"prefixes": [key]}).encode()
        self._request("DELETE", f"object/{quote(self.bucket, safe='')}", body, "application/json")

    def signed_url(self, key: str, seconds: int) -> str | None:
        body = json.dumps({"expiresIn": seconds}).encode()
        answer = self._request("POST", f"object/sign/{self._path(key)}", body, "application/json")
        signed = json.loads(answer)["signedURL"]  # relative to /storage/v1
        return f"{self.base}/{signed.lstrip('/')}"
