"""Load test: the busiest owner journeys against a demo business ten times its usual size.

Skipped unless LOAD_TEST=1 (it seeds thousands of rows). CI runs it in its own job:

    LOAD_TEST=1 LOAD_REPORT=load-report.md uv run pytest tests/load -s

Each journey is the set of requests one screen of the business app makes when it opens
(see apps/business-app/src/app/(tabs)). Requests run in-process, one after another, so the
numbers measure the API and the database, not the network, and are a little pessimistic for
screens that fetch in parallel. The same journeys run on the standard demo (1x) for comparison.
The budgets are loose on purpose: they catch a missing index or an N+1, not a slow runner.
"""

import dataclasses
import os
import random
import statistics
import time
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.seed import seed
from app.seed.common import CLIENTS, STUDIO
from tests.conftest import AuthHeaders, local_today

pytestmark = pytest.mark.skipif(
    os.environ.get("LOAD_TEST") != "1", reason="set LOAD_TEST=1 to run the load test"
)

SCALE = 10
MONTHS = 3
RUNS = 15
# p95 of one whole journey on the 10x business, in seconds.
BUDGET_SECONDS = 2.0

Request = tuple[str, dict]
Journey = Callable[[str, str], list[Request]]


def journeys() -> dict[str, list[Request]]:
    today = local_today()
    end = today - timedelta(days=1)
    period = {"start": (end - timedelta(days=29)).isoformat(), "end": end.isoformat()}
    return {
        "Today (schedule, attention, usage)": [
            ("/sessions", {"start": today.isoformat(), "days": 7}),
            ("/attention", {}),
            ("/resources", {}),
            ("/services", {"active": "true"}),
            ("/billing/usage", {}),
        ],
        "Clients (list, search, filters)": [
            ("/clients", {"limit": 30}),
            ("/clients", {"limit": 30, "search": "נ"}),
            ("/clients", {"limit": 30, "plan": "none"}),
            ("/clients", {"limit": 30, "absent_days": 14}),
        ],
        "Numbers (reports)": [
            (
                "/metrics",
                {
                    **period,
                    "keys": [
                        "revenue",
                        "active_clients",
                        "attendance",
                        "occupancy",
                        "no_show_rate",
                        "new_clients",
                    ],
                },
            ),
            ("/metrics/breakdown/service", period),
            ("/metrics/members-at-risk", {"days": 14}),
            ("/metrics/revenue/series", {**period, "grain": "day"}),
        ],
    }


@dataclasses.dataclass
class Result:
    journey: str
    p50: float
    p95: float
    worst: float


def measure(client: TestClient, headers: dict[str, str]) -> list[Result]:
    results = []
    for name, requests in journeys().items():
        times = []
        for run in range(RUNS + 1):
            started = time.perf_counter()
            for path, params in requests:
                response = client.get(path, params=params, headers=headers)
                assert response.status_code == 200, (path, response.status_code, response.text)
            elapsed = time.perf_counter() - started
            if run:  # the first pass warms the caches and connection pool
                times.append(elapsed)
        times.sort()
        results.append(
            Result(
                name,
                statistics.median(times),
                times[max(0, round(0.95 * len(times)) - 1)],
                times[-1],
            )
        )
    return results


def seed_owner(engine: Engine, clients: int) -> tuple[UUID, UUID]:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": f"load-{owner}@example.com"},
        )
        email = f"load-{owner}@example.com"
        spec = dataclasses.replace(STUDIO, clients=clients)
        tenant_id = seed(connection, email, MONTHS, random.Random(7), spec)
    return owner, tenant_id


def sizes(engine: Engine, tenant_id: UUID) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            table: connection.execute(
                text(f"SELECT count(*) FROM app.{table} WHERE tenant_id = :t"), {"t": tenant_id}
            ).scalar_one()
            for table in ("clients", "sessions", "bookings", "payments")
        }


def test_busiest_journeys_at_ten_times_the_demo(
    client: TestClient, auth: AuthHeaders, engine: Engine
) -> None:
    rows = []
    for scale in (1, SCALE):
        owner, tenant_id = seed_owner(engine, CLIENTS * scale)
        with engine.begin() as connection:
            connection.execute(text("ANALYZE"))
        rows.append((scale, sizes(engine, tenant_id), measure(client, auth(owner, tenant_id))))

    lines = [
        "# Load test: business app journeys",
        "",
        f"Standard demo studio (1x, {CLIENTS} clients) against {SCALE}x "
        f"({CLIENTS * SCALE} clients), {MONTHS} months of history each. "
        f"{RUNS} timed runs per journey, in-process, "
        "requests one after another (seconds per whole journey).",
        "",
        "| Data | Clients | Sessions | Bookings | Payments |",
        "|---|---|---|---|---|",
    ]
    for scale, size, _ in rows:
        lines.append(
            f"| {scale}x | {size['clients']} | {size['sessions']} | {size['bookings']} "
            f"| {size['payments']} |"
        )
    lines += [
        "",
        "| Journey | 1x p50 | 1x p95 | 10x p50 | 10x p95 | 10x worst |",
        "|---|---|---|---|---|---|",
    ]
    for one, many in zip(rows[0][2], rows[1][2], strict=True):
        lines.append(
            f"| {many.journey} | {one.p50:.3f} | {one.p95:.3f} | {many.p50:.3f} "
            f"| {many.p95:.3f} | {many.worst:.3f} |"
        )
    report = "\n".join(lines) + "\n"
    print("\n" + report)
    if path := os.environ.get("LOAD_REPORT"):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(report)

    for result in rows[1][2]:
        assert result.p95 < BUDGET_SECONDS, f"{result.journey}: p95 {result.p95:.2f}s"
