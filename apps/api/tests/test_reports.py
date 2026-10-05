import random
from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.seed import seed
from tests.conftest import AuthHeaders, add_member, local_today


def demo(engine: Engine, auth: AuthHeaders) -> dict:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": f"{owner}@example.com"},
        )
        tenant_id = seed(connection, f"{owner}@example.com", 3, random.Random(3))
    return {"tenant_id": tenant_id, "headers": auth(owner, tenant_id)}


def test_metrics_for_a_month_with_comparison(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    studio = demo(engine, auth)
    end = local_today() - timedelta(days=1)
    start = end - timedelta(days=29)

    response = client.get(
        "/metrics", params={"start": start, "end": end}, headers=studio["headers"]
    )

    assert response.status_code == 200
    values = {m["key"]: m for m in response.json()}
    assert set(values) >= {"revenue", "active_clients", "occupancy", "no_show_rate"}
    assert values["revenue"]["value"] > 0 and values["revenue"]["unit"] == "money"
    assert 0 < values["occupancy"]["value"] <= 100
    assert 0 <= values["no_show_rate"]["value"] < 20
    assert values["no_show_rate"]["higher_is_better"] is False
    assert values["attendance"]["previous"] > 0  # the month before has history too


def test_weekly_series_fills_empty_weeks(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    studio = demo(engine, auth)
    end = local_today()
    start = end - timedelta(days=7 * 8)

    points = client.get(
        "/metrics/attendance/series",
        params={"start": start, "end": end, "grain": "week"},
        headers=studio["headers"],
    ).json()

    assert len(points) in (9, 10)
    assert all(date.fromisoformat(p["bucket"]).weekday() == 0 for p in points)
    assert sum(p["value"] for p in points) > 0
    no_series = client.get(
        "/metrics/occupancy/series",
        params={"start": start, "end": end},
        headers=studio["headers"],
    )
    assert no_series.status_code == 422


def test_reports_need_permission_and_are_isolated(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    demo_studio = demo(engine, auth)
    desk = uuid4()
    add_member(engine, demo_studio["tenant_id"], desk, "front_desk")
    params = {"start": local_today() - timedelta(days=30), "end": local_today()}

    assert (
        client.get(
            "/metrics", params=params, headers=auth(desk, demo_studio["tenant_id"])
        ).status_code
        == 403
    )
    empty = client.get("/metrics", params=params, headers=studio["headers"]).json()
    assert {m["key"]: m["value"] for m in empty}["revenue"] == 0  # the other studio's money
    bad = client.get(
        "/metrics", params={"start": "2026-02-01", "end": "2026-01-01"}, headers=studio["headers"]
    )
    assert bad.status_code == 422


def test_breakdowns_add_up_to_the_metrics(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    studio = demo(engine, auth)
    end = local_today() - timedelta(days=1)
    start = end - timedelta(days=29)
    period = {"start": start, "end": end}
    metrics = {
        m["key"]: m["value"]
        for m in client.get("/metrics", params=period, headers=studio["headers"]).json()
    }

    by_service = client.get(
        "/metrics/breakdown/service", params=period, headers=studio["headers"]
    ).json()
    by_instructor = client.get(
        "/metrics/breakdown/instructor", params=period, headers=studio["headers"]
    ).json()
    by_slot = client.get(
        "/metrics/breakdown/time_slot", params=period, headers=studio["headers"]
    ).json()

    for rows in (by_service, by_instructor, by_slot):
        assert sum(r["attended"] for r in rows) == metrics["attendance"]
        assert sum(r["sessions"] for r in rows) == metrics["sessions_held"]
    assert len(by_service) == 5 and all(r["label"] for r in by_service)
    assert all(0 <= r["occupancy"] <= 100 for r in by_service)
    weekday, hour = by_slot[0]["key"].split("-")
    assert 1 <= int(weekday) <= 7 and 0 <= int(hour) <= 23


def test_members_at_risk(client: TestClient, engine: Engine, auth: AuthHeaders) -> None:
    studio = demo(engine, auth)

    members = client.get(
        "/metrics/members-at-risk", params={"days": 14}, headers=studio["headers"]
    ).json()

    reasons = {m["reason"] for m in members}
    assert reasons == {"inactive", "plan_ending"}  # the demo has both scenarios
    cutoff = local_today() - timedelta(days=14)
    for member in members:
        if member["reason"] == "inactive":
            # inactive means no visit for `days` exact days; a visit on the cutoff date
            # earlier in the day than now already counts
            last = member["last_visit"]
            assert last is None or date.fromisoformat(last) <= cutoff
        else:
            ends = date.fromisoformat(member["plan_ends_on"])
            assert ends < local_today() + timedelta(days=14)
    bad = client.get("/metrics/members-at-risk", params={"days": 3}, headers=studio["headers"])
    assert bad.status_code == 422
