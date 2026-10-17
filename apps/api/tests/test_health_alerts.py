from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app import jobs
from app.core import metrics
from app.messaging.alerts import alert_team
from app.messaging.email import LogSender
from app.messaging.push import LogPushSender
from tests.conftest import AuthHeaders, make_staff


def owner_with_phone(engine: Engine) -> tuple:
    user = uuid4()
    email = make_staff(engine, user, "owner")
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.push_tokens (user_id, token, platform) VALUES (:u, :t, 'ios')"),
            {"u": user, "t": f"ExponentPushToken[{user}]"},
        )
    return user, email


def test_alert_reaches_owners_by_push_and_email(engine: Engine) -> None:
    user, email = owner_with_phone(engine)
    employee = uuid4()
    make_staff(engine, employee, "employee")
    push, mail = LogPushSender(), LogSender()
    with engine.begin() as connection:
        result = alert_team(connection, "Job failed", "details", push, mail)

    assert result.pushed >= 1 and result.emailed >= 1
    assert any(f"ExponentPushToken[{user}]" in tokens for tokens, _, _ in push.sent)
    sent_to = {message.to for message in mail.sent}
    assert email in sent_to and f"{employee}@example.com" not in sent_to


def test_alert_skips_a_channel_that_is_off(engine: Engine) -> None:
    owner_with_phone(engine)
    with engine.begin() as connection:
        result = alert_team(connection, "t", "b", None, None)
    assert result.pushed == 0 and result.emailed == 0 and result.recipients >= 1


def test_a_failing_job_alerts_once(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    alerts: list[str] = []
    monkeypatch.setattr(jobs.runner, "notify_team", lambda _e, title, _b: alerts.append(title))

    def boom(_conn) -> None:
        raise RuntimeError("provider down")

    monkeypatch.setitem(jobs.JOBS, "boom", boom)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            jobs.run_job(engine, "boom")
    assert alerts == ["MyBiz job failed: boom"]

    monkeypatch.setitem(jobs.JOBS, "boom", lambda _conn: "ok")
    jobs.run_job(engine, "boom")
    monkeypatch.setitem(jobs.JOBS, "boom", boom)
    with pytest.raises(RuntimeError):
        jobs.run_job(engine, "boom")
    assert len(alerts) == 2  # it recovered, then failed again


def test_health_page_data(client: TestClient, engine: Engine, auth: AuthHeaders) -> None:
    metrics.reset()
    owner = uuid4()
    make_staff(engine, owner, "owner")
    headers = auth(owner)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO app.job_runs (job, finished_at, ok, result)"
                " VALUES ('send-messages', now() - interval '40 hours', true, 'done')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO app.job_runs (job, finished_at, ok, result)"
                " VALUES ('purge-expired', now(), false, 'RuntimeError: x')"
            )
        )
    client.get("/platform/me", headers=headers)

    health = client.get("/platform/health", headers=headers)

    assert health.status_code == 200, health.text
    body = health.json()
    by_job = {job["job"]: job for job in body["jobs"]}
    assert by_job["send-messages"]["late"] is True
    assert (
        by_job["purge-expired"]["last_ok"] is False and by_job["purge-expired"]["failures_24h"] == 1
    )
    assert body["database_bytes"] > 0
    assert any(route["route"] == "GET /platform/me" for route in body["routes"])


def test_health_page_needs_the_usage_permission(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    employee = uuid4()
    make_staff(engine, employee, "employee")
    assert client.get("/platform/health", headers=auth(employee)).status_code == 403


def test_metrics_keep_recent_crashes_and_percentiles() -> None:
    metrics.reset()
    for ms in range(1, 101):
        metrics.record_request("GET", "/x", 200, float(ms))
    metrics.record_request("GET", "/x", 500, 5.0, "rid", None, "ValueError")
    stat = metrics.route_stats()[0]
    assert stat.count == 101 and 94 <= stat.p95_ms <= 96
    assert metrics.recent_errors()[0].request_id == "rid"
    metrics.reset()
