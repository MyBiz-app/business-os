"""Rate limits per caller (#51)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.rate_limit import MemoryStore, Rule, limiter

RULES = (
    Rule("public-write", "/public/", 2, methods=frozenset({"POST"})),
    Rule("public", "/public/", 3),
    Rule("all", "/", 5),
)


def make_app(now: list[float], *, trust_forwarded: bool = False) -> TestClient:
    app = FastAPI()
    app.middleware("http")(
        limiter(MemoryStore(), trust_forwarded=trust_forwarded, rules=RULES, clock=lambda: now[0])
    )

    @app.get("/public/page")
    def page() -> dict:
        return {"ok": True}

    @app.post("/public/form")
    def form() -> dict:
        return {"ok": True}

    @app.get("/private")
    def private() -> dict:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    return TestClient(app)


def test_public_calls_are_limited_per_window() -> None:
    now = [1000.0]
    client = make_app(now)
    assert [client.get("/public/page").status_code for _ in range(4)] == [200, 200, 200, 429]
    blocked = client.get("/public/page")
    assert blocked.json() == {"detail": "too_many_requests"}
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    now[0] += 60  # the next window
    assert client.get("/public/page").status_code == 200


def test_writes_have_a_tighter_limit_and_everything_a_ceiling() -> None:
    now = [0.0]
    client = make_app(now)
    assert [client.post("/public/form").status_code for _ in range(3)] == [200, 200, 429]
    # Two posts got through (the third stopped at its own limit), so three more calls fit
    # under the ceiling of 5.
    assert [client.get("/private").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert all(client.get("/health").status_code == 200 for _ in range(10))  # never limited


def test_visitors_are_counted_apart_behind_the_proxy() -> None:
    now = [0.0]
    trusted = make_app(now, trust_forwarded=True)
    for visitor in ("203.0.113.1", "203.0.113.2"):
        headers = {"X-Forwarded-For": f"{visitor}, 10.0.0.1"}
        codes = [trusted.get("/public/page", headers=headers).status_code for _ in range(3)]
        assert codes == [200, 200, 200]
    # Not behind a trusted proxy, the header is ignored: one caller.
    direct = make_app(now)
    codes = [
        direct.get("/public/page", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(4)
    ]
    assert codes[-1] == 429


def test_rate_limits_are_on_outside_local_development() -> None:
    assert Settings(environment="local").rate_limits_on is False
    assert Settings(environment="staging").rate_limits_on is True
    assert Settings(environment="production", rate_limits=False).rate_limits_on is False


def test_ready_checks_the_database(client: TestClient) -> None:
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ok", "database": "ok"}
