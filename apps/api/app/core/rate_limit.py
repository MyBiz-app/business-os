"""Rate limits per caller (#51): a burst of requests from one address gets 429 before it reaches
the database. The tightest limits are on what anyone can call without signing in (`/public/…`:
a business's join page, the quote link, inquiries, the contact form, signed file links); signed-in
calls get a generous ceiling that a person never reaches.

Counts live in a store behind a small interface: the built-in in-memory store counts per API
process, which is enough for one instance; with several instances a shared store (Redis) plugs in
here without touching the rules."""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class Rule:
    name: str
    prefix: str
    limit: int  # requests per window per address
    window: int = 60  # seconds
    methods: frozenset[str] | None = None  # None: every method


# A request counts against every rule it matches (a public form post: public-write, public, all).
RULES: tuple[Rule, ...] = (
    Rule("public-write", "/public/", 20, methods=frozenset({"POST", "PUT", "PATCH", "DELETE"})),
    Rule("public", "/public/", 120),
    Rule("webhooks", "/webhooks/", 600),
    Rule("all", "/", 1200),
)
EXEMPT = ("/health", "/health/ready")


class LimiterStore(Protocol):
    def hit(self, key: str, window: int, now: float) -> tuple[int, float]:
        """Counts one request for `key` in the current window; returns the count so far and
        when the window ends."""
        ...


class MemoryStore:
    """Fixed windows per key, kept in this process; old windows are dropped as it goes."""

    def __init__(self, max_keys: int = 50_000) -> None:
        self._counts: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def hit(self, key: str, window: int, now: float) -> tuple[int, float]:
        start = now - now % window
        with self._lock:
            if len(self._counts) >= self._max_keys:
                self._counts = {k: v for k, v in self._counts.items() if v[0] + window > now}
            current_start, count = self._counts.get(key, (start, 0))
            if current_start != start:
                count = 0
            count += 1
            self._counts[key] = (start, count)
        return count, start + window


def client_address(request: Request, trust_forwarded: bool) -> str:
    """The caller's address; behind the hosting proxy, the first address it forwarded."""
    if trust_forwarded:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def limiter(
    store: LimiterStore,
    *,
    trust_forwarded: bool,
    rules: tuple[Rule, ...] = RULES,
    clock: Callable[[], float] = time.time,
):
    """The middleware: counts the request against each matching rule; over a limit, answers 429
    with Retry-After."""

    async def middleware(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in EXEMPT:
            return await call_next(request)
        address = client_address(request, trust_forwarded)
        now = clock()
        for rule in rules:
            if not path.startswith(rule.prefix):
                continue
            if rule.methods is not None and request.method not in rule.methods:
                continue
            count, ends = store.hit(f"{rule.name}:{address}", rule.window, now)
            if count > rule.limit:
                return JSONResponse(
                    {"detail": "too_many_requests"},
                    status_code=429,
                    headers={"Retry-After": str(max(1, math.ceil(ends - now)))},
                )
        return await call_next(request)

    return middleware
