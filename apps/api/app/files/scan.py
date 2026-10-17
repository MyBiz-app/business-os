"""Virus scanning of uploads (GL3): a switch, not yet a service.

Scanning needs a ClamAV daemon (a separate Render service, about $7 a month) or a cloud scanning
service, so it is built and left OFF (`API_FILE_SCAN_PROVIDER=none`). The interface and the
ClamAV adapter are here and tested; turning it on is one step in docs/deploy/go-live-checklist.md.
When it is on, a scanner that cannot be reached refuses the upload (fail closed)."""

import socket
import struct
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, status

from app.core.config import get_settings


class ScanUnavailable(RuntimeError):
    """The scanner could not be reached or gave no verdict."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None = None


class FileScanProvider(Protocol):
    def scan(self, content: bytes) -> ScanResult: ...


class NoScan:
    """The default: scanning is off, every file passes (the type and size checks still apply)."""

    def scan(self, content: bytes) -> ScanResult:
        return ScanResult(clean=True)


class ClamAVScan:
    """A ClamAV daemon (clamd) over TCP, using its INSTREAM command."""

    CHUNK = 64 * 1024

    def __init__(self, host: str, port: int = 3310, timeout: float = 20.0) -> None:
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, content: bytes) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as conn:
                conn.sendall(b"zINSTREAM\0")
                for start in range(0, len(content), self.CHUNK):
                    chunk = content[start : start + self.CHUNK]
                    conn.sendall(struct.pack("!I", len(chunk)) + chunk)
                conn.sendall(struct.pack("!I", 0))
                reply = b""
                while not reply.endswith(b"\0") and (part := conn.recv(4096)):
                    reply += part
        except OSError as error:
            raise ScanUnavailable(str(error)) from error
        verdict = reply.rstrip(b"\0\n").decode("utf-8", "replace")
        if verdict.endswith("OK"):
            return ScanResult(clean=True)
        if verdict.endswith("FOUND"):
            return ScanResult(clean=False, signature=verdict.removeprefix("stream: ")[:-6].strip())
        raise ScanUnavailable(verdict or "empty reply")


def scanner() -> FileScanProvider:
    settings = get_settings()
    if settings.file_scan_provider == "clamav":
        return ClamAVScan(settings.file_scan_host, settings.file_scan_port)
    return NoScan()


def ensure_clean(content: bytes) -> None:
    """422 `file_infected` for a file the scanner flags, 503 `scan_unavailable` when scanning is on
    but cannot answer. With scanning off this does nothing."""
    try:
        result = scanner().scan(content)
    except ScanUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="scan_unavailable"
        ) from error
    if not result.clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="file_infected"
        )
