"""Structured JSON logs with a request id.

One line per request (method, route, status, duration) and one per unhandled error, each carrying
the request id the caller also gets back in `X-Request-ID`. Logs hold ids only, never personal
data: no names, emails, query strings or bodies."""

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID = 64
_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")

logger = logging.getLogger("app")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id := request_id_var.get():
            entry["request_id"] = request_id
        if tenant_id := tenant_id_var.get():
            entry["tenant_id"] = tenant_id
        fields = getattr(record, "fields", None)
        if fields:
            entry.update(fields)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _StdoutHandler(logging.StreamHandler):
    """Writes to whatever `sys.stdout` is now (so tests can capture it)."""

    def __init__(self) -> None:
        super().__init__()

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout

    @stream.setter
    def stream(self, _value) -> None:
        pass


def configure_logging(level: str = "INFO") -> None:
    """Send the app's logs to stdout as JSON (idempotent)."""
    # Alembic's logging setup (run by the tests and migrations) disables existing loggers.
    logger.disabled = False
    if any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        logger.setLevel(level)
        return
    handler = _StdoutHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def log(level: int, message: str, **fields: object) -> None:
    logger.log(level, message, extra={"fields": fields})


def _clean_request_id(value: str | None) -> str:
    """Keep a caller-supplied id only when it is short and plain; otherwise make a new one."""
    if value and len(value) <= _MAX_REQUEST_ID and set(value) <= _ID_CHARS:
        return value
    return uuid4().hex


def _tenant_of(request: Request) -> str | None:
    try:
        return str(UUID(request.headers.get("X-Tenant-Id", "")))
    except ValueError:
        return None


async def request_logging(request: Request, call_next):
    """Middleware: assign a request id, log the request, turn crashes into a stable 500 body."""
    request_id = _clean_request_id(request.headers.get(REQUEST_ID_HEADER))
    request_id_var.set(request_id)
    tenant_id_var.set(_tenant_of(request))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled error",
            extra={"fields": {"method": request.method, "path": request.url.path}},
        )
        response = JSONResponse(
            {"detail": "Internal server error", "request_id": request_id}, status_code=500
        )
    route = request.scope.get("route")
    log(
        logging.INFO,
        "request",
        method=request.method,
        # The route template, not the URL: ids in paths stay out of the logs.
        path=getattr(route, "path", request.url.path if response.status_code == 404 else None),
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
