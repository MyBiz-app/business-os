"""In-memory request timing and recent crashes, for the console's health page.

Per process and reset on restart: it answers "is it slow or failing right now", not "last month"
(the logs and Sentry keep the history). Only route templates and ids are kept, no personal data."""

import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

SAMPLES_PER_ROUTE = 500
MAX_ROUTES = 300  # templates are a fixed set; this only bounds a pathological 404 flood
RECENT_ERRORS = 20

_lock = threading.Lock()
_durations: dict[str, deque[float]] = {}
_errors: deque["RecentError"] = deque(maxlen=RECENT_ERRORS)


@dataclass(frozen=True)
class RecentError:
    at: datetime
    request_id: str | None
    method: str
    path: str | None
    tenant_id: str | None
    status: int
    error: str | None


@dataclass(frozen=True)
class RouteStat:
    route: str
    count: int
    p50_ms: float
    p95_ms: float


def record_request(
    method: str,
    path: str | None,
    status: int,
    duration_ms: float,
    request_id: str | None = None,
    tenant_id: str | None = None,
    error: str | None = None,
) -> None:
    key = f"{method} {path}" if path else None
    with _lock:
        if key and (key in _durations or len(_durations) < MAX_ROUTES):
            _durations.setdefault(key, deque(maxlen=SAMPLES_PER_ROUTE)).append(duration_ms)
        if status >= 500:
            _errors.append(
                RecentError(datetime.now(UTC), request_id, method, path, tenant_id, status, error)
            )


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def route_stats(limit: int = 15) -> list[RouteStat]:
    """The busiest routes first, with the median and 95th-percentile time of the recent calls."""
    with _lock:
        snapshot = {key: list(values) for key, values in _durations.items()}
    stats = [
        RouteStat(key, len(values), _percentile(values, 0.5), _percentile(values, 0.95))
        for key, values in snapshot.items()
        if values
    ]
    return sorted(stats, key=lambda stat: stat.count, reverse=True)[:limit]


def recent_errors() -> list[RecentError]:
    with _lock:
        return list(reversed(_errors))


def reset() -> None:
    with _lock:
        _durations.clear()
        _errors.clear()
