"""Scheduled agent tasks (round 5, A10): the schedule rules, the card, the board, the runner."""

import datetime as dt
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import scheduled, task_runner
from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_assistant import FakeProvider, ask, calls, conversation, enable_ai_pro, says
from tests.test_assistant import use_provider as use_provider
from tests.test_bookings import new_client, new_session

UTC = dt.UTC
JERUSALEM = "Asia/Jerusalem"


def at(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_schedule_rules() -> None:
    daily = scheduled.build_schedule("daily", "08:00")
    # 2026-10-16 is a Friday; Jerusalem is UTC+3 until the clocks go back on 2026-10-25.
    assert scheduled.next_run(daily, JERUSALEM, at(2026, 10, 16, 4, 0)) == at(2026, 10, 16, 5, 0)
    assert scheduled.next_run(daily, JERUSALEM, at(2026, 10, 16, 5, 0)) == at(2026, 10, 17, 5, 0)
    # After the change it is still 08:00 local, which is now 06:00 UTC.
    assert scheduled.next_run(daily, JERUSALEM, at(2026, 10, 25, 12, 0)) == at(2026, 10, 26, 6, 0)

    sunday_and_tuesday = scheduled.build_schedule("weekly", "09:30", weekdays=[6, 1, 6])
    assert sunday_and_tuesday["weekdays"] == [1, 6]
    assert scheduled.next_run(sunday_and_tuesday, JERUSALEM, at(2026, 10, 16, 8, 0)) == at(
        2026, 10, 18, 6, 30
    )

    monthly = scheduled.build_schedule("monthly", "07:00", day_of_month=1)
    assert scheduled.next_run(monthly, JERUSALEM, at(2026, 10, 16)) == at(2026, 11, 1, 5, 0)

    once = scheduled.build_schedule("once", "18:00", date="2026-10-18")
    assert scheduled.next_run(once, JERUSALEM, at(2026, 10, 16)) == at(2026, 10, 18, 15, 0)
    assert scheduled.next_run(once, JERUSALEM, at(2026, 10, 19)) is None


@pytest.mark.parametrize(
    "arguments",
    [
        ("sometimes", "08:00"),
        ("daily", "25:00"),
        ("weekly", "08:00"),
        ("weekly", "08:00", None, [7]),
        ("monthly", "08:00", None, None, 31),
        ("once", "08:00"),
    ],
)
def test_bad_schedules_are_refused(arguments: tuple[Any, ...]) -> None:
    with pytest.raises(scheduled.ScheduleError):
        scheduled.build_schedule(*arguments)


def schedule_card(client: TestClient, headers: dict, args: dict[str, Any], use_provider) -> dict:
    """Has the agent propose a task and returns the card (nothing is created yet)."""
    use_provider(FakeProvider([calls("schedule_task", args), says("Please confirm the card.")]))
    turns = ask(client, headers, conversation(client, headers), "schedule it").json()["turns"]
    [card] = turns[-1]["pending_actions"]
    return card


def tomorrow() -> str:
    return (local_today() + timedelta(days=1)).isoformat()


def report_task(**changes: Any) -> dict[str, Any]:
    return {
        "kind": "agent_run",
        "title": "Weekly summary",
        "frequency": "weekly",
        "date": "",
        "time": "08:00",
        "weekdays": [6],
        "day_of_month": 0,
        "instruction": "Summarise the week and send me the numbers.",
        "action_tool": "",
        "action_args_json": "",
        **changes,
    }


def make_due(engine: Engine, task_id: str, minutes_ago: int = 1) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.ai_scheduled_tasks SET next_run_at = now() - make_interval(mins => :m) "
                "WHERE id = :id"
            ),
            {"m": minutes_ago, "id": task_id},
        )


def run_due(engine: Engine, provider: FakeProvider | None = None) -> dict[str, int]:
    with engine.connect() as connection:
        return task_runner.run_due_tasks(connection, provider)


def test_an_agent_run_is_created_through_a_card_and_runs_read_only(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    headers = studio["headers"]
    card = schedule_card(client, headers, report_task(), use_provider)

    assert card["tool_name"] == "schedule_task"
    assert card["preview"]["title"] == "Weekly summary"
    assert client.get("/ai/tasks", headers=headers).json()["tasks"] == []  # not before Confirm

    # The AI Basic module allows 10 live tasks.
    assert client.get("/ai/tasks", headers=headers).json()["limit"] == 10
    confirmed = client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    assert confirmed.json()["status"] == "executed"
    board = client.get("/ai/tasks", headers=headers).json()
    [task] = board["tasks"]
    assert (task["title"], task["kind"], task["status"]) == (
        "Weekly summary",
        "agent_run",
        "active",
    )
    assert task["schedule"]["weekdays"] == [6]
    assert task["next_run_at"] is not None and board["precise_timing"] is False

    # At run time the agent works on its own: it may only propose, and the proposal waits days.
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    enable_ai_pro(client, studio)
    provider = FakeProvider([
        calls("get_metrics", {"metrics": ["revenue"], "start_date": "2026-09-01",
                              "end_date": "2026-09-30"}),
        calls("book_client", {"session_id": session_id, "client_id": dana}),
        says("Revenue is flat. I proposed booking Dana into Pilates."),
    ])  # fmt: skip
    make_due(engine, task["id"])
    assert run_due(engine, provider) == {"ok": 1, "failed": 0, "skipped": 0}

    [run] = client.get(f"/ai/tasks/{task['id']}/runs", headers=headers).json()
    assert run["status"] == "ok" and "Revenue is flat" in run["summary"]
    assert run["credits"] > 0 and len(run["pending_action_ids"]) == 1
    assert (
        "scheduled task that runs by itself"
        in provider.calls[0]["messages"][0]["content"][1]["text"]
    )
    after = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    assert after["waiting_for_approval"] == 1 and after["status"] == "active"
    assert after["last_run_at"] is not None
    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert roster == []  # nothing happened without the user's approval

    # The proposal can be approved from the chat the run opened, days later.
    [pending] = client.get(f"/ai/conversations/{run['conversation_id']}", headers=headers).json()[
        "turns"
    ][-1]["pending_actions"]
    with engine.connect() as connection:
        days = connection.execute(
            text(
                "SELECT extract(day FROM expires_at - created_at) FROM app.pending_actions "
                "WHERE id = :id"
            ),
            {"id": pending["id"]},
        ).scalar_one()
    assert days >= 2
    assert (
        client.post(f"/ai/pending-actions/{pending['id']}/confirm", headers=headers).json()[
            "status"
        ]
        == "executed"
    )


def test_a_scheduled_action_is_checked_again_when_it_runs(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    card = schedule_card(
        client,
        headers,
        report_task(
            kind="action",
            title="Book Dana",
            frequency="once",
            date=tomorrow(),
            time="07:00",
            weekdays=[],
            instruction="",
            action_tool="book_client",
            action_args_json=f'{{"session_id": "{session_id}", "client_id": "{dana}"}}',
        ),
        use_provider,
    )
    assert card["preview"]["action"]["service"] == "Pilates"
    # Looking at the action to preview it created no booking and no card of its own.
    assert client.get(f"/sessions/{session_id}/bookings", headers=headers).json() == []
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM app.pending_actions WHERE tool_name = 'book_client'")
            ).scalar_one()
            == 0
        )

    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    [task] = client.get("/ai/tasks", headers=headers).json()["tasks"]
    make_due(engine, task["id"])
    assert run_due(engine) == {"ok": 1, "failed": 0, "skipped": 0}

    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert [b["client_name"] for b in roster] == ["Dana"]
    [done] = client.get("/ai/tasks", headers=headers).json()["tasks"]
    assert done["status"] == "done" and done["last_status"] == "ok"
    with engine.connect() as connection:
        audit = connection.execute(text("SELECT action FROM app.audit_log")).scalars().all()
    assert "assistant.scheduled.book_client" in audit
    assert run_due(engine) == {"ok": 0, "failed": 0, "skipped": 0}  # a done task never repeats


def test_a_failing_run_is_retried_once_then_the_task_fails(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    card = schedule_card(
        client,
        headers,
        report_task(
            kind="action", title="Book Dana", frequency="once", date=tomorrow(), time="07:00",
            weekdays=[], instruction="", action_tool="book_client",
            action_args_json=f'{{"session_id": "{session_id}", "client_id": "{dana}"}}',
        ),
        use_provider,
    )  # fmt: skip
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    [task] = client.get("/ai/tasks", headers=headers).json()["tasks"]
    # Dana gets booked by hand first, so the scheduled booking cannot succeed.
    booked = client.post(
        f"/sessions/{session_id}/bookings", json={"client_id": dana}, headers=headers
    )
    assert booked.status_code == 201

    make_due(engine, task["id"])
    assert run_due(engine)["failed"] == 1
    again = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    assert again["status"] == "active" and again["next_run_at"] is not None  # retry in 15 minutes
    make_due(engine, task["id"])
    assert run_due(engine)["failed"] == 1
    final = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    assert final["status"] == "failed" and final["last_status"] == "failed"


def test_a_repeating_task_pauses_after_three_failures(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    headers = studio["headers"]
    card = schedule_card(client, headers, report_task(), use_provider)
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    [task] = client.get("/ai/tasks", headers=headers).json()["tasks"]
    use_provider(None)  # no AI configured: every run fails
    for _ in range(3):
        make_due(engine, task["id"])
        assert run_due(engine)["failed"] == 1
    paused = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    assert (paused["status"], paused["status_reason"]) == ("paused", "failed_3_times")

    # Resuming starts fresh; the owner can also delete it.
    resumed = client.patch(f"/ai/tasks/{task['id']}", json={"status": "active"}, headers=headers)
    assert resumed.json()["status"] == "active" and resumed.json()["status_reason"] is None
    assert client.delete(f"/ai/tasks/{task['id']}", headers=headers).status_code == 204
    assert client.get("/ai/tasks", headers=headers).json()["tasks"] == []


def test_a_task_of_someone_who_lost_access_is_paused(
    client: TestClient, studio: dict, auth: AuthHeaders, use_provider, engine: Engine
) -> None:
    owner_headers = studio["headers"]
    manager_id, other_id = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], manager_id, "front_desk")
    add_member(engine, studio["tenant_id"], other_id, "front_desk")
    manager = {"headers": auth(manager_id, studio["tenant_id"])}
    card = schedule_card(client, manager["headers"], report_task(), use_provider)
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=manager["headers"])
    [task] = client.get("/ai/tasks", headers=manager["headers"]).json()["tasks"]

    # The owner sees it too (ai.manage); a colleague's board stays their own.
    assert len(client.get("/ai/tasks", headers=owner_headers).json()["tasks"]) == 1
    other_headers = auth(other_id, studio["tenant_id"])
    assert client.get("/ai/tasks", headers=other_headers).json()["tasks"] == []
    assert (
        client.patch(
            f"/ai/tasks/{task['id']}", json={"title": "Mine now"}, headers=owner_headers
        ).status_code
        == 404
    )  # others may pause or delete a task, not rewrite it

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM app.tenant_members WHERE user_id = :u"), {"u": manager_id}
        )
    make_due(engine, task["id"])
    assert run_due(engine, FakeProvider([])) == {"ok": 0, "failed": 0, "skipped": 1}
    [paused] = client.get("/ai/tasks", headers=owner_headers).json()["tasks"]
    assert (paused["status"], paused["status_reason"]) == ("paused", "member_gone")


def test_task_limit_and_a_late_one_time_task(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    headers = studio["headers"]
    card = schedule_card(client, headers, report_task(), use_provider)
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    with engine.begin() as connection:  # nine more, to reach AI Basic's limit of ten
        connection.execute(
            text("""
                INSERT INTO app.ai_scheduled_tasks
                    (tenant_id, created_by, agent_key, kind, title, instruction, schedule,
                     time_zone, next_run_at)
                SELECT tenant_id, created_by, agent_key, kind, title || n, instruction, schedule,
                       time_zone, next_run_at
                FROM app.ai_scheduled_tasks, generate_series(1, 9) AS n
            """)
        )
    use_provider(FakeProvider([calls("schedule_task", report_task(title="One too many")),
                               says("ok")]))  # fmt: skip
    turns = ask(client, headers, conversation(client, headers), "one more").json()["turns"]
    assert turns[-1]["pending_actions"] == []  # the tool refused: the business is at its limit

    once = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.ai_scheduled_tasks SET schedule = CAST(:s AS jsonb) WHERE id = :id"),
            {"s": '{"type": "once", "date": "2020-01-01", "time": "08:00"}', "id": once["id"]},
        )
    make_due(engine, once["id"], minutes_ago=60 * 30)  # found 30 hours late
    assert run_due(engine) == {"ok": 0, "failed": 0, "skipped": 0}
    [run] = client.get(f"/ai/tasks/{once['id']}/runs", headers=headers).json()
    assert (run["status"], run["error"]) == ("skipped", "missed")


def test_run_now_and_editing_the_time(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    headers = studio["headers"]
    card = schedule_card(client, headers, report_task(), use_provider)
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    [task] = client.get("/ai/tasks", headers=headers).json()["tasks"]

    moved = client.patch(
        f"/ai/tasks/{task['id']}",
        json={"schedule": {"frequency": "daily", "time": "06:15"}, "title": "Daily summary"},
        headers=headers,
    ).json()
    assert (
        moved["schedule"] == {"type": "daily", "time": "06:15"}
        and moved["title"] == "Daily summary"
    )
    assert (
        client.patch(
            f"/ai/tasks/{task['id']}",
            json={"schedule": {"frequency": "daily", "time": "99:99"}},
            headers=headers,
        ).status_code
        == 422
    )

    use_provider(FakeProvider([says("All quiet this week.")]))
    ran = client.post(f"/ai/tasks/{task['id']}/run", headers=headers)
    assert ran.status_code == 200 and ran.json()["status"] == "ok"
    assert ran.json()["summary"] == "All quiet this week."
    after = client.get("/ai/tasks", headers=headers).json()["tasks"][0]
    assert after["next_run_at"] == moved["next_run_at"]  # running now left the schedule alone


def test_the_tick_needs_the_internal_token(client: TestClient) -> None:
    assert client.post("/internal/jobs/tick").status_code == 401
    wrong = client.post("/internal/jobs/tick", headers={"X-Internal-Token": "nope"})
    assert wrong.status_code == 401


def test_other_businesses_never_see_a_task(
    client: TestClient, studio: dict, auth: AuthHeaders, use_provider
) -> None:
    card = schedule_card(client, studio["headers"], report_task(), use_provider)
    client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=studio["headers"])
    [task] = client.get("/ai/tasks", headers=studio["headers"]).json()["tasks"]

    stranger = uuid4()
    other = UUID(client.post(
        "/tenants",
        json={"name": "Other", "vertical": "fitness", "locale": "he",
              "time_zone": JERUSALEM, "currency": "ILS"},
        headers=auth(stranger),
    ).json()["id"])  # fmt: skip
    other_headers = auth(stranger, other)
    client.put("/tenants/current/modules", json={"modules": {"client_app": 1, "ai_basic": 1}},
               headers=other_headers)  # fmt: skip
    assert client.get("/ai/tasks", headers=other_headers).json()["tasks"] == []
    assert client.delete(f"/ai/tasks/{task['id']}", headers=other_headers).status_code == 404
