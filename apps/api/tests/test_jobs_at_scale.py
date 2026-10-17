"""Background jobs at scale (go-live GL14): one run of a job at a time, one business failing
does not stop the others, the outbox is fair between businesses, deletions go in batches."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, text

from app import jobs
from app.core.tenant_scope import tenant_scope
from app.jobs import run_job
from app.messaging import outbox


def make_businesses(engine: Engine, count: int, messages: dict[int, int]) -> list[uuid.UUID]:
    """`count` businesses, each with a client; messages[i] queued messages for business i
    (two for the others)."""
    tenants = [uuid.uuid4() for _ in range(count)]
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app.tenants (id, name, vertical, locale, time_zone, currency)
                SELECT t, 'Biz ' || t, 'fitness', 'en', 'Asia/Jerusalem', 'ILS'
                FROM unnest(CAST(:ids AS uuid[])) AS t
            """),
            {"ids": tenants},
        )
        conn.execute(
            text("""
                INSERT INTO app.clients (tenant_id, first_name, phone)
                SELECT t, 'Dana', '050-1111111' FROM unnest(CAST(:ids AS uuid[])) AS t
            """),
            {"ids": tenants},
        )
        for index, tenant in enumerate(tenants):
            conn.execute(
                text("""
                    INSERT INTO app.messages
                        (tenant_id, client_id, channel, to_phone, body, status, created_at)
                    SELECT :t, (SELECT id FROM app.clients WHERE tenant_id = :t), 'whatsapp',
                           '050-1111111', 'Hi', 'queued', now() - make_interval(secs => n)
                    FROM generate_series(1, :n) AS n
                """),
                {"t": tenant, "n": messages.get(index, 2)},
            )
    return tenants


def sent_per_business(engine: Engine) -> dict[uuid.UUID, int]:
    with engine.connect() as conn:
        return dict(
            conn.execute(
                text("""
                    SELECT tenant_id, count(*) FROM app.messages WHERE status = 'sent'
                    GROUP BY tenant_id
                """)
            ).all()
        )


def test_a_business_with_a_huge_queue_does_not_hold_back_the_others(engine: Engine) -> None:
    tenants = make_businesses(engine, 200, {0: 1200})  # 199 businesses with 2 messages each
    with engine.begin() as conn:
        counts = outbox.send_messages(conn)
    assert counts["sent"] == outbox.BATCH
    sent = sent_per_business(engine)
    assert all(sent.get(tenant) == 2 for tenant in tenants[1:])  # every other business, in full
    assert sent[tenants[0]] == outbox.BATCH - 199 * 2


def test_a_failed_message_waits_longer_before_the_next_try(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_args):
        def send(_message):
            raise ConnectionError("provider down")

        return SimpleNamespace(
            instance=SimpleNamespace(send=send, simulated=False), info=SimpleNamespace(name="x")
        )

    monkeypatch.setattr(outbox, "choose", down)
    make_businesses(engine, 1, {0: 1})
    waits = []
    for _ in range(3):
        with engine.begin() as conn:
            outbox.send_messages(conn)
            outbox.send_messages(conn)  # straight away again: it is not due yet
            attempts, due = conn.execute(
                text("SELECT attempts, next_attempt_at FROM app.messages")
            ).one()
            waits.append((due - datetime.now(UTC)).total_seconds() / 60)
            assert attempts == len(waits)
            conn.execute(text("UPDATE app.messages SET next_attempt_at = now()"))
    assert [round(wait) for wait in waits] == [5, 10, 20]


def test_one_business_failing_leaves_the_others_and_is_recorded(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants = make_businesses(engine, 3, {})

    def job(conn):
        for tenant in tenants:
            with tenant_scope(conn, tenant):
                conn.execute(
                    text("UPDATE app.tenants SET name = 'done' WHERE id = :t"), {"t": tenant}
                )
                if tenant == tenants[1]:
                    raise RuntimeError("bad data")
        return "ran"

    monkeypatch.setitem(jobs.JOBS, "remind-sessions", job)
    assert run_job(engine, "remind-sessions") == "ran"
    with engine.connect() as conn:
        names = dict(conn.execute(text("SELECT id, name FROM app.tenants")).all())
        run = conn.execute(text("SELECT ok, succeeded, failed, result FROM app.job_runs")).one()
    assert names[tenants[0]] == names[tenants[2]] == "done"
    assert names[tenants[1]] != "done"  # rolled back alone
    assert run.ok and (run.succeeded, run.failed) == (2, 1)
    assert str(tenants[1]) in run.result


def test_a_job_never_runs_twice_at_once(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    ran = []
    monkeypatch.setitem(jobs.JOBS, "remind-plans", lambda conn: ran.append(1) or "ran")
    with engine.connect() as other:  # another run of the same job holds the lock
        other.execute(
            text("SELECT pg_advisory_lock(hashtextextended(:key, 0))"),
            {"key": f"{jobs.LOCK_PREFIX}remind-plans"},
        )
        assert str(run_job(engine, "remind-plans")).startswith("skipped")
        assert ran == []
        other.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
            {"key": f"{jobs.LOCK_PREFIX}remind-plans"},
        )
    assert run_job(engine, "remind-plans") == "ran"  # the lock is free again
    assert run_job(engine, "remind-plans") == "ran"  # and a finished run released its own
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ok, result FROM app.job_runs ORDER BY id")).all()
    assert [row.ok for row in rows] == [False, True, True]
    assert rows[0].result.startswith("skipped")


def test_retention_deletes_in_batches(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "PURGE_BATCH", 3)
    old = datetime.now(UTC) - timedelta(days=800)
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app.contact_requests (name, email, locale, created_at)
                SELECT 'Dana', 'd' || n || '@example.com', 'en', :old
                FROM generate_series(1, 10) AS n
            """),
            {"old": old},
        )
        conn.execute(
            text(
                "INSERT INTO app.contact_requests (name, email, locale)"
                " VALUES ('New', 'new@example.com', 'en')"
            )
        )
    with engine.begin() as conn:
        deleted = jobs.purge_expired(conn)
    assert deleted["contact_requests"] == 10
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app.contact_requests")).scalar_one() == 1
