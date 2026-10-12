from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import monitoring
from app.core.config import Settings
from app.main import create_app


def test_monitoring_stays_off_without_a_dsn() -> None:
    assert monitoring.init_monitoring(Settings()) is False
    assert monitoring.monitoring_enabled() is False


def test_scrub_removes_personal_data_from_events() -> None:
    event = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/clients?email=a@b.com",
            "data": {"name": "Dana"},
            "cookies": {"s": "x"},
            "headers": {"Authorization": "Bearer t"},
            "query_string": "email=a@b.com",
        },
        "user": {"email": "a@b.com"},
    }

    clean = monitoring.scrub_event(event)

    assert clean["request"] == {"method": "POST", "url": "https://api.example.com/clients"}
    assert "user" not in clean


def test_crash_is_reported_with_request_and_tenant_ids(monkeypatch) -> None:
    sent: list[tuple] = []
    monkeypatch.setattr(
        "app.core.logging.capture_exception", lambda error, rid, tid: sent.append((error, rid, tid))
    )
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("x")

    tenant = "11111111-1111-1111-1111-111111111111"
    response = TestClient(app, raise_server_exceptions=False).get(
        "/boom", headers={"X-Request-ID": "rid-9", "X-Tenant-Id": tenant}
    )

    assert response.status_code == 500
    assert len(sent) == 1 and sent[0][1:] == ("rid-9", tenant)


def test_dsn_turns_monitoring_on(monkeypatch) -> None:
    started: dict = {}
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: started.update(kw))
    monkeypatch.setattr(monitoring, "_enabled", False)

    settings = Settings(sentry_dsn=SecretStr("https://k@o1.ingest.sentry.io/1"))

    assert monitoring.init_monitoring(settings) is True
    assert started["send_default_pii"] is False
    assert started["before_send"] is monitoring.scrub_event
    monkeypatch.setattr(monitoring, "_enabled", False)
