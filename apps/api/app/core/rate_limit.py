"""Rate limits per caller (#51): a burst of requests from one address gets 429 before it reaches
the database. The tightest limits are on what anyone can call without signing in (`/public/…`:
a business's join page, the quote link, inquiries, the contact form, signed file links); signed-in
calls get a generous ceiling that a person never reaches.

Counts live in a store behind a small interface: the built-in in-memory store counts per API
process, which is enough for one instance; with several instances a shared store (Redis) plugs in
here without touching the rules. `RedisStore` is that shared store; it is used only when
`API_RATE_LIMIT_REDIS_URL` is set (off by default)."""

import hmac
import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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


class RedisStore:
    """Fixed windows shared by every API instance, kept in Redis. If Redis cannot be reached the
    request is counted by a local `MemoryStore` instead, so an outage never takes the API down."""

    def __init__(self, client, prefix: str = "rl", fallback: LimiterStore | None = None) -> None:
        self._client = client
        self._prefix = prefix
        self._fallback = fallback or MemoryStore()

    @classmethod
    def from_url(cls, url: str) -> "RedisStore":
        import redis  # imported here: only needed when a Redis URL is configured

        return cls(redis.Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25))

    def hit(self, key: str, window: int, now: float) -> tuple[int, float]:
        start = now - now % window
        redis_key = f"{self._prefix}:{key}:{int(start)}"
        try:
            pipe = self._client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window + 1)
            count = int(pipe.execute()[0])
        except Exception:
            logger.warning("rate limit store unavailable; counting locally", exc_info=True)
            return self._fallback.hit(key, window, now)
        return count, start + window


def build_store(redis_url: str | None) -> LimiterStore:
    """The in-process store unless a Redis URL is configured."""
    return RedisStore.from_url(redis_url) if redis_url else MemoryStore()


VISITOR_HEADER = "x-visitor-address"
INTERNAL_TOKEN_HEADER = "x-internal-token"  # noqa: S105 (a header name, not a secret)


def client_address(
    request: Request, trust_forwarded: bool, internal_token: str | None = None
) -> str:
    """The caller's address, never a value the caller can choose freely.

    The web server (which sees the real visitor) may name the visitor in `X-Visitor-Address`, but
    only together with the shared `X-Internal-Token`. Otherwise, behind the hosting proxy, the
    address is the right-most `X-Forwarded-For` entry: the one the proxy itself appended, after
    anything the caller sent. Without a trusted proxy, the connection's own address."""
    if internal_token:
        supplied = request.headers.get(INTERNAL_TOKEN_HEADER, "")
        visitor = request.headers.get(VISITOR_HEADER, "").strip()
        if visitor and hmac.compare_digest(supplied.encode(), internal_token.encode()):
            return visitor
    if trust_forwarded:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


def limiter(
    store: LimiterStore,
    *,
    trust_forwarded: bool,
    internal_token: str | None = None,
    rules: tuple[Rule, ...] = RULES,
    clock: Callable[[], float] = time.time,
):
    """The middleware: counts the request against each matching rule; over a limit, answers 429
    with Retry-After."""

    async def middleware(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in EXEMPT:
            return await call_next(request)
        address = client_address(request, trust_forwarded, internal_token)
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
