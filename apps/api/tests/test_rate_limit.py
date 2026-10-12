"""Rate limits per caller (#51)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import MemoryStore, RedisStore, Rule, build_store, limiter

RULES = (
    Rule("public-write", "/public/", 2, methods=frozenset({"POST"})),
    Rule("public", "/public/", 3),
    Rule("all", "/", 5),
)


def make_app(
    now: list[float], *, trust_forwarded: bool = False, internal_token: str | None = None
) -> TestClient:
    app = FastAPI()
    app.middleware("http")(
        limiter(
            MemoryStore(),
            trust_forwarded=trust_forwarded,
            internal_token=internal_token,
            rules=RULES,
            clock=lambda: now[0],
        )
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
        headers = {"X-Forwarded-For": f"10.9.9.9, {visitor}"}
        codes = [trusted.get("/public/page", headers=headers).status_code for _ in range(3)]
        assert codes == [200, 200, 200]
    # Not behind a trusted proxy, the header is ignored: one caller.
    direct = make_app(now)
    codes = [
        direct.get("/public/page", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(4)
    ]
    assert codes[-1] == 429


def test_a_spoofed_forwarded_for_does_not_reset_the_count() -> None:
    now = [0.0]
    trusted = make_app(now, trust_forwarded=True)
    # The caller invents a new leading address each time; the proxy appended the real one last.
    codes = [
        trusted.get(
            "/public/page", headers={"X-Forwarded-For": f"198.51.100.{i}, 203.0.113.7"}
        ).status_code
        for i in range(4)
    ]
    assert codes[-1] == 429


def test_web_server_names_the_visitor_only_with_the_shared_token() -> None:
    now = [0.0]
    app = make_app(now, trust_forwarded=True, internal_token="s3cret")
    for visitor in ("203.0.113.1", "203.0.113.2"):
        headers = {"X-Internal-Token": "s3cret", "X-Visitor-Address": visitor}
        assert [app.get("/public/page", headers=headers).status_code for _ in range(3)] == [200] * 3
    # Without (or with a wrong) token the claimed visitor is ignored: one caller.
    codes = [
        app.get(
            "/public/page",
            headers={"X-Internal-Token": "nope", "X-Visitor-Address": f"192.0.2.{i}"},
        ).status_code
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


class FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self._store = store
        self._ops: list[str] = []

    def incr(self, key: str) -> None:
        self._ops.append(key)

    def expire(self, key: str, seconds: int) -> None:
        pass

    def execute(self) -> list[int]:
        key = self._ops[0]
        self._store[key] = self._store.get(key, 0) + 1
        return [self._store[key]]


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self.data)


class BrokenRedis:
    def pipeline(self):
        raise ConnectionError("down")


def test_redis_store_counts_per_window_and_key() -> None:
    store = RedisStore(FakeRedis())
    assert [store.hit("a", 60, 100.0)[0] for _ in range(3)] == [1, 2, 3]
    assert store.hit("b", 60, 100.0)[0] == 1
    assert store.hit("a", 60, 119.0) == (4, 120.0)  # same window (60..120)
    assert store.hit("a", 60, 121.0) == (1, 180.0)  # next window


def test_redis_store_falls_back_to_local_counts_when_redis_is_down() -> None:
    store = RedisStore(BrokenRedis())
    assert [store.hit("a", 60, 100.0)[0] for _ in range(2)] == [1, 2]


def test_store_is_in_memory_unless_a_redis_url_is_set() -> None:
    assert isinstance(build_store(None), MemoryStore)
    assert isinstance(build_store("redis://localhost:6379/0"), RedisStore)
