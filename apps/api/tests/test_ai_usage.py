# ruff: noqa: F811, F401
"""AI usage and who may use it (round 7, R8): the meter, the daily pace, a person's own switch and
limit, and the AI users a module includes."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_ai_spend import spend_credits
from tests.test_assistant import FakeProvider, ask, conversation, says, use_provider


def test_the_meter_shows_the_business_to_managers_and_only_the_person_to_others(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    included = client.get("/ai/spend", headers=headers).json()["credits_included"]
    spend_credits(engine, included * 0.85)

    meter = client.get("/ai/meter", headers=headers).json()
    assert meter["business"]["included"] == included
    assert meter["business"]["percent"] == 85.0 and meter["business"]["level"] == "warn"
    assert meter["business"]["reach_date"] is not None or meter["pace_percent"] > 85
    assert meter["level"] == "warn"
    assert meter["person"]["day_limit"] is None  # the owner has no daily pace

    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    mine = client.get("/ai/meter", headers=auth(desk, studio["tenant_id"])).json()
    assert mine["business"] is None
    assert mine["person"]["day_limit"] == round(included * 0.15)


def test_a_daily_pace_stops_one_person_but_not_the_owner(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, use_provider
) -> None:
    use_provider(FakeProvider([says("Hi.")] * 4))
    headers = studio["headers"]
    included = client.get("/ai/spend", headers=headers).json()["credits_included"]
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    desk_headers = auth(desk, studio["tenant_id"])

    spend_credits(engine, included * 0.16, user_id=str(desk))  # over 15% of the pool today
    blocked = ask(client, desk_headers, conversation(client, desk_headers), "hi")
    assert blocked.status_code == 409 and blocked.json()["detail"] == "ai_daily_pace_reached"

    spend_credits(engine, included * 0.16, user_id=str(studio["owner"]))
    assert ask(client, headers, conversation(client, headers), "hi").status_code == 200

    raised = client.put(f"/ai/members/{desk}", json={"daily_percent": 50}, headers=headers).json()
    assert raised["daily_percent"] == 50 and raised["day_limit"] == round(included / 2)
    assert ask(client, desk_headers, conversation(client, desk_headers), "hi").status_code == 200


def test_a_person_switch_overrides_the_role(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    teacher, desk = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], teacher, "staff")
    add_member(engine, studio["tenant_id"], desk, "front_desk")

    assert client.get(f"/ai/members/{teacher}", headers=headers).json()["has_access"] is False
    on = client.put(f"/ai/members/{teacher}", json={"ai_access": True}, headers=headers).json()
    assert on["has_access"] is True and on["ai_access"] is True
    assert client.get("/ai/meter", headers=auth(teacher, studio["tenant_id"])).status_code == 200

    off = client.put(f"/ai/members/{desk}", json={"ai_access": False}, headers=headers).json()
    assert off["has_access"] is False
    assert client.get("/ai/meter", headers=auth(desk, studio["tenant_id"])).status_code == 403

    back = client.put(f"/ai/members/{desk}", json={"ai_access": None}, headers=headers).json()
    assert back["has_access"] is True
    owner = client.put(f"/ai/members/{studio['owner']}", json={"ai_access": False}, headers=headers)
    assert owner.status_code == 409 and owner.json()["detail"] == "owner_always_has_ai"


def test_a_personal_monthly_limit_is_set_and_cleared_from_the_card(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    saved = client.put(f"/ai/members/{desk}", json={"monthly_credits": 40}, headers=headers).json()
    assert saved["monthly_credits"] == 40
    assert client.get("/ai/spend", headers=headers).json()["limits"] == [
        {"kind": "user", "key": str(desk), "monthly_credits": 40}
    ]
    cleared = client.put(
        f"/ai/members/{desk}", json={"monthly_credits": None}, headers=headers
    ).json()
    assert cleared["monthly_credits"] is None


def test_ai_users_are_capped_by_the_module_and_extra_users_add_credits(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    client.put(
        "/tenants/current/modules", json={"modules": {"crm": 1, "ai_basic": 1}}, headers=headers
    )
    base = client.get("/ai/usage/breakdown", headers=headers).json()
    assert base["ai_users_allowed"] == 3 and base["extra_ai_users"] == 0
    pool = client.get("/ai/spend", headers=headers).json()["credits_included"]

    members = [uuid4() for _ in range(4)]
    for member in members:
        add_member(engine, studio["tenant_id"], member, "staff")
    for member in members[:3]:
        ok = client.put(f"/ai/members/{member}", json={"ai_access": True}, headers=headers)
        assert ok.status_code == 200, ok.text
    full = client.put(f"/ai/members/{members[3]}", json={"ai_access": True}, headers=headers)
    assert full.status_code == 409 and full.json()["detail"] == "ai_users_full"

    more = client.put("/ai/extra-users", json={"extra_ai_users": 1}, headers=headers).json()
    assert more["ai_users_allowed"] == 4 and more["ai_users_count"] == 3
    assert client.get("/ai/spend", headers=headers).json()["credits_included"] == pool + 150
    assert client.put(
        f"/ai/members/{members[3]}", json={"ai_access": True}, headers=headers
    ).json()["has_access"]
    refused = client.put("/ai/extra-users", json={"extra_ai_users": 0}, headers=headers)
    assert refused.status_code == 409 and refused.json()["detail"] == "ai_users_in_use"


def test_scheduled_runs_are_told_apart_from_questions(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    spend_credits(engine, 12)
    kinds = {
        r["key"]: r["credits"]
        for r in client.get("/ai/usage/breakdown", headers=headers).json()["by_kind"]
    }
    assert kinds == {"asked": 12.0, "scheduled": 0.0}
