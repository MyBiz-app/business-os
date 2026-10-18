"""Payroll pushes: the owner's reminder on the 1st and 5th, and "your payslip is ready"."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.payroll_notices import notify_payslips_ready, remind_payroll
from app.messaging.push import LogPushSender
from tests.test_payroll_runs import _setup, open_payroll
from tests.test_payslips import _approve

TOKEN = "ExponentPushToken[owner0000000000]"


def add_token(engine: Engine, user_id: UUID, token: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        conn.execute(
            text("INSERT INTO app.push_tokens (user_id, token, platform) VALUES (:u, :t, 'ios')"),
            {"u": user_id, "t": token},
        )


def test_the_owner_is_reminded_on_the_1st_and_5th_until_last_month_is_approved(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    open_payroll(client, studio["headers"])
    add_token(engine, studio["owner"], TOKEN)
    push = LogPushSender()

    def remind(day: int) -> dict[str, int]:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
            return remind_payroll(conn, push, datetime(2026, 4, day, 12, tzinfo=UTC))

    assert remind(1) == {"businesses": 1, "pushed": 1}
    tokens, title, _body = push.sent[0]
    assert tokens == [TOKEN] and "03/2026" in title  # last month, in the business's language
    assert remind(1) == {"businesses": 0, "pushed": 0}  # once a day, however often the job runs
    assert remind(2) == {"businesses": 0, "pushed": 0}
    assert remind(5) == {"businesses": 1, "pushed": 1}

    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        conn.execute(
            text("""
                INSERT INTO app.payroll_runs (tenant_id, period, currency, stage, approved_at)
                VALUES (:t, '2026-03-01', 'ILS', 'approved', now())
            """),
            {"t": studio["tenant_id"]},
        )
    assert remind(5) == {"businesses": 0, "pushed": 0}


def test_a_business_without_the_payroll_module_is_not_reminded(
    studio: dict, engine: Engine
) -> None:
    add_token(engine, studio["owner"], TOKEN)
    push = LogPushSender()
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        result = remind_payroll(conn, push, datetime(2026, 4, 1, 12, tzinfo=UTC))
    assert result == {"businesses": 0, "pushed": 0} and push.sent == []


def test_everyone_with_a_line_is_pushed_once_when_the_run_is_approved(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    add_token(engine, studio["coach"], TOKEN)
    push = LogPushSender()

    def notify() -> dict[str, int]:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
            return notify_payslips_ready(conn, push)

    assert notify() == {"runs": 0, "pushed": 0}  # nothing approved yet
    _approve(client, ctx["headers"], ctx)
    assert notify() == {"runs": 1, "pushed": 1}
    tokens, _title, body = push.sent[0]
    assert tokens == [TOKEN] and "03/2026" in body
    assert notify() == {"runs": 0, "pushed": 0}  # announced once per run
