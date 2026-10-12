from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text

from app import jobs
from app.jobs import MAX_HOURS, OPTIONAL, late_jobs, run_group, run_job


def runs(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text("SELECT job, finished_at, ok, result FROM app.job_runs ORDER BY id")
            ).mappings()
        ]


def test_a_run_is_recorded(engine: Engine) -> None:
    result = run_job(engine, "extend-series")
    [run] = runs(engine)
    assert run["job"] == "extend-series"
    assert run["ok"] is True
    assert run["finished_at"] is not None
    assert run["result"] == str(result)


def test_a_failed_run_is_recorded_and_raised(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(conn):
        raise RuntimeError("provider down")

    monkeypatch.setitem(jobs.JOBS, "send-messages", broken)
    with pytest.raises(RuntimeError):
        run_job(engine, "send-messages")
    [run] = runs(engine)
    assert run["ok"] is False
    assert run["result"] == "RuntimeError: provider down"


def test_a_group_keeps_going_after_a_failure(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(conn):
        raise RuntimeError("boom")

    monkeypatch.setitem(jobs.JOBS, "remind-sessions", broken)
    failed = run_group(engine, ["remind-sessions", "remind-plans"])
    assert failed == ["remind-sessions"]
    assert [(run["job"], run["ok"]) for run in runs(engine)] == [
        ("remind-sessions", False),
        ("remind-plans", True),
    ]


def test_late_jobs(engine: Engine) -> None:
    now = datetime.now(UTC)
    with engine.begin() as conn:
        never_ran = {item["job"] for item in late_jobs(conn, now)}
        assert never_ran == set(MAX_HOURS) - OPTIONAL  # emails count only once they've run
        for job in MAX_HOURS:
            conn.execute(
                text("""
                INSERT INTO app.job_runs (job, started_at, finished_at, ok)
                VALUES (:job, :at, :at, true)
            """),
                {"job": job, "at": now - timedelta(hours=1)},
            )
        assert late_jobs(conn, now) == []
        # A daily job that last succeeded two days ago is late, even if it failed since.
        conn.execute(
            text("""
            UPDATE app.job_runs SET started_at = :at, finished_at = :at
            WHERE job = 'extend-series'
        """),
            {"at": now - timedelta(days=2)},
        )
        conn.execute(
            text("""
            INSERT INTO app.job_runs (job, finished_at, ok) VALUES ('extend-series', now(), false)
        """)
        )
        # Hourly jobs four hours behind are late too, optional ones included once they ran.
        conn.execute(
            text("""
            UPDATE app.job_runs SET finished_at = :at
            WHERE job IN ('publish-shifts', 'notify-shifts')
        """),
            {"at": now - timedelta(hours=4)},
        )
        assert [item["job"] for item in late_jobs(conn, now)] == [
            "extend-series",
            "publish-shifts",
            "notify-shifts",
        ]
