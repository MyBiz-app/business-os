"""Storage: files the system keeps (logos, documents). The built-in `database` provider keeps
the bytes in Postgres, which is fine for small files; an object store (S3-compatible, Supabase
Storage) plugs in here for larger ones."""

from dataclasses import dataclass
from typing import Protocol

from app.providers.registry import register


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
