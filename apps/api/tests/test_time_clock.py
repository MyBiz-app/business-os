"""Time clock: clocking in and out, corrections, month approval and overtime arithmetic."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.schedule.time_clock import ClockRules, compute, split_by_day
from tests.conftest import AuthHeaders, local_today
from tests.test_workspace import at

ZONE = "Asia/Jerusalem"


def test_hours_are_split_at_local_midnight() -> None:
    start = datetime(2026, 10, 12, 20, 0, tzinfo=ZoneInfo(ZONE))
    end = start + timedelta(hours=8)
    assert split_by_day(start, end, ZONE) == {date(2026, 10, 12): 4, date(2026, 10, 13): 4}


def test_daily_overtime_steps_and_rest_day() -> None:
    rules = ClockRules(work_days_per_week=5)
    # Monday 12 h: 8.6 regular, 2 at 125%, 1.4 at 150%. Saturday 4 h at 150%.
    result = compute({date(2026, 10, 12): 12, date(2026, 10, 17): 4}, rules)
    assert (result.regular, result.tier1, result.tier2, result.rest_day) == (8.6, 2, 1.4, 4)
    assert result.total == 16
    assert result.weighted == round(8.6 + 2 * 1.25 + 1.4 * 1.5 + 4 * 1.5, 2)


def test_six_day_week_uses_the_shorter_day() -> None:
    result = compute({date(2026, 10, 12): 9}, ClockRules(work_days_per_week=6))
    assert (result.regular, result.tier1) == (8, 1)


def test_hours_past_the_week_limit_are_overtime() -> None:
    # Sunday to Thursday, 9 h a day short of the daily limit would be 8.6; use 8.5 h x 5 = 42.5.
    week = {date(2026, 10, 11) + timedelta(days=i): 8.5 for i in range(5)}
    result = compute(week, ClockRules())
    assert result.regular == 42 and result.tier1 == 0.5


def test_clock_in_out_and_a_manager_fixes_the_month(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    owner, coach_headers = studio["headers"], auth(studio["coach"], studio["tenant_id"])
    coach = str(studio["coach"])
    location = studio["location"]["id"]
    month = local_today().strftime("%Y-%m")

    idle = client.get("/me/time-clock", headers=coach_headers).json()
    assert idle["open_entry"] is None
    assert client.post("/me/time-clock/clock-out", headers=coach_headers).status_code == 409

    started = client.post("/me/time-clock/clock-in", json={}, headers=coach_headers)
    assert started.status_code == 201
    assert started.json()["source"] == "clock" and started.json()["clock_out"] is None
    again = client.post("/me/time-clock/clock-in", json={}, headers=coach_headers)
    assert again.status_code == 409 and again.json()["detail"] == "already_clocked_in"
    assert (
        client.get("/me/time-clock", headers=coach_headers).json()["open_entry"]["id"]
        == (started.json()["id"])
    )
    # The month cannot be approved while a clock still runs.
    blocked = client.put(
        f"/time-clock/people/{coach}/approval", params={"month": month}, headers=owner
    )
    assert blocked.status_code == 409 and blocked.json()["detail"] == "entry_open"
    stopped = client.post("/me/time-clock/clock-out", headers=coach_headers)
    assert stopped.status_code == 200 and stopped.json()["clock_out"] is not None

    # Staff do not see or change the month.
    assert client.get("/time-clock/month", headers=coach_headers).status_code == 403

    # A manager adds forgotten time, with a reason, and it shows in the month.
    day = at(-3, 9)
    added = client.post(
        "/time-clock/entries",
        json={
            "user_id": coach,
            "location_id": location,
            "clock_in": day,
            "clock_out": at(-3, 18),
            "reason": " Forgot to clock in ",
        },
        headers=owner,
    )
    assert added.status_code == 201, added.text
    entry = added.json()
    assert entry["source"] == "manual" and entry["correction_reason"] == "Forgot to clock in"
    noreason = client.post(
        "/time-clock/entries",
        json={
            "user_id": coach,
            "location_id": location,
            "clock_in": at(-5, 9),
            "clock_out": at(-5, 10),
            "reason": " ",
        },
        headers=owner,
    )
    assert noreason.status_code == 422
    clash = client.post(
        "/time-clock/entries",
        json={
            "user_id": coach,
            "location_id": location,
            "clock_in": at(-3, 17),
            "clock_out": at(-3, 19),
            "reason": "x",
        },
        headers=owner,
    )
    assert clash.status_code == 409 and clash.json()["detail"] == "entry_overlap"

    fixed = client.patch(
        f"/time-clock/entries/{entry['id']}",
        json={"clock_out": at(-3, 19), "reason": "Left at seven"},
        headers=owner,
    )
    assert fixed.status_code == 200 and fixed.json()["correction_reason"] == "Left at seven"

    month = (local_today() - timedelta(days=3)).strftime("%Y-%m")  # where the added entry lies
    detail = client.get(f"/time-clock/people/{coach}", params={"month": month}, headers=owner)
    assert detail.status_code == 200
    body = detail.json()
    assert body["worked"]["total"] >= 10 and body["approved"] is False
    people = client.get("/time-clock/month", params={"month": month}, headers=owner).json()[
        "people"
    ]
    row = next(p for p in people if p["user_id"] == coach)
    assert row["corrections"] >= 1 and row["worked"]["total"] >= 10

    # Approving locks the month; reopening unlocks it.
    assert (
        client.put(
            f"/time-clock/people/{coach}/approval", params={"month": month}, headers=owner
        ).status_code
        == 204
    )
    locked = client.patch(
        f"/time-clock/entries/{entry['id']}",
        json={"clock_out": at(-3, 17), "reason": "x"},
        headers=owner,
    )
    assert locked.status_code == 409 and locked.json()["detail"] == "month_approved"
    assert (
        client.delete(
            f"/time-clock/people/{coach}/approval", params={"month": month}, headers=owner
        ).status_code
        == 204
    )
    gone = client.delete(
        f"/time-clock/entries/{entry['id']}", params={"reason": "Duplicate"}, headers=owner
    )
    assert gone.status_code == 204
    assert (
        client.delete(
            f"/time-clock/entries/{entry['id']}", params={"reason": "x"}, headers=owner
        ).status_code
        == 404
    )


def test_the_overtime_rules_are_data(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    default = client.get("/time-clock/rules", headers=owner).json()
    assert default["week_hours"] == 42 and default["day_hours_5"] == 8.6
    saved = client.put(
        "/time-clock/rules",
        json={**default, "work_days_per_week": 6, "tier1_hours": 1},
        headers=owner,
    )
    assert saved.status_code == 200 and saved.json()["work_days_per_week"] == 6
    assert client.get("/time-clock/rules", headers=owner).json()["tier1_hours"] == 1
