"""Rate limits per caller (#51)."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import MemoryStore, RedisStore, Rule, TenantQuota, build_store, limiter
from tests.conftest import AuthHeaders
from tests.test_tenants import STUDIO

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


def test_tenant_quota_counts_per_business_and_window() -> None:
    quota = TenantQuota(MemoryStore(), 2)
    a, b = uuid4(), uuid4()
    quota.check(a, clock=lambda: 100.0)
    quota.check(a, clock=lambda: 100.0)
    with pytest.raises(HTTPException) as blocked:
        quota.check(a, clock=lambda: 100.0)
    assert blocked.value.status_code == 429 and blocked.value.detail == "tenant_rate_limited"
    assert blocked.value.headers is not None and int(blocked.value.headers["Retry-After"]) >= 1
    quota.check(b, clock=lambda: 100.0)  # another business is not affected
    quota.check(a, clock=lambda: 121.0)  # the next window


def test_tenant_quota_zero_means_off() -> None:
    quota = TenantQuota(MemoryStore(), 0)
    for _ in range(5):
        quota.check(uuid4())


def test_one_busy_business_does_not_block_another(client: TestClient, auth: AuthHeaders) -> None:
    client.app.state.tenant_quota = TenantQuota(MemoryStore(), 3)  # type: ignore[attr-defined]
    owners = [uuid4(), uuid4()]
    tenants = [
        UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
        for owner in owners
    ]
    busy = auth(owners[0], tenants[0])
    codes = [client.get("/clients", headers=busy).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    blocked = client.get("/clients", headers=busy)
    assert blocked.json() == {"detail": "tenant_rate_limited"}
    assert "Retry-After" in blocked.headers
    assert client.get("/clients", headers=auth(owners[1], tenants[1])).status_code == 200
    # Nothing is counted for a caller who is not a member (their header proves nothing).
    outsider = auth(uuid4(), tenants[1])
    assert [client.get("/clients", headers=outsider).status_code for _ in range(5)] == [403] * 5
