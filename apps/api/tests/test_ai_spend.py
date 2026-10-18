# ruff: noqa: F811, F401
"""AI spend controls (round 5, A2): pay-as-you-go extra credits (off by default), the cap, limits
per role and per person, alerts at 80/100/150/200% and the modules that were "coming soon"."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member
from tests.test_assistant import FakeProvider, ask, conversation, says, use_provider


def spend_credits(engine: Engine, credits: float, user_id: str | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details)
                SELECT id, 'ai_credits', :q, CAST(:details AS jsonb) FROM app.tenants
            """),
            {"q": credits, "details": json.dumps({"user_id": user_id} if user_id else {})},
        )


def test_payg_is_off_by_default_and_the_plan_limit_stops_questions(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    headers = studio["headers"]
    spend = client.get("/ai/spend", headers=headers).json()
    assert spend["payg_enabled"] is False and spend["payg_cap_minor"] is None
    assert spend["credits_limit"] == spend["credits_included"] > 0
    assert spend["price_per_100_minor"] == 800  # ILS

    spend_credits(engine, spend["credits_included"] + 1)
    response = ask(client, headers, conversation(client, headers), "hi")
    assert response.status_code == 409 and response.json()["detail"] == "ai_limit_reached"


def test_payg_without_a_cap_keeps_working_and_bills_the_extra(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    headers = studio["headers"]
    included = client.get("/ai/spend", headers=headers).json()["credits_included"]

    on = client.put("/ai/spend", json={"payg_enabled": True}, headers=headers).json()
    assert on["payg_enabled"] is True and on["credits_limit"] is None

    spend_credits(engine, included + 250)
    response = ask(client, headers, conversation(client, headers), "hi")
    assert response.status_code == 200, response.text
    spend = client.get("/ai/spend", headers=headers).json()
    assert spend["extra_credits"] >= 250
    assert spend["extra_minor"] >= 2000  # 250 credits at 8.00 per 100
    assert client.get("/billing/usage", headers=headers).json()["ai_extra_minor"] >= 2000


def test_payg_cap_stops_questions_when_reached(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    use_provider(FakeProvider([says("Hi."), says("Hi.")]))
    headers = studio["headers"]
    included = client.get("/ai/spend", headers=headers).json()["credits_included"]

    capped = client.put(
        "/ai/spend", json={"payg_enabled": True, "payg_cap_minor": 1200}, headers=headers
    ).json()
    assert capped["credits_limit"] == included + 150  # 12.00 buys 150 credits at 8.00 per 100

    spend_credits(engine, included + 100)
    assert ask(client, headers, conversation(client, headers), "hi").status_code == 200
    spend_credits(engine, 100)
    response = ask(client, headers, conversation(client, headers), "hi")
    assert response.status_code == 409 and response.json()["detail"] == "ai_limit_reached"

    off = client.put("/ai/spend", json={"payg_enabled": False}, headers=headers).json()
    assert off["credits_limit"] == included and off["extra_minor"] == 0


def test_payg_needs_an_ai_module_and_the_manage_permission(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"crm": 1}}, headers=headers)
    refused = client.put("/ai/spend", json={"payg_enabled": True}, headers=headers)
    assert refused.status_code == 409 and refused.json()["detail"] == "ai_module_required"

    front = uuid4()
    add_member(engine, studio["tenant_id"], front, "front_desk")
    assert client.get("/ai/spend", headers=auth(front, studio["tenant_id"])).status_code == 403


def test_limits_per_role_and_per_person(
    client: TestClient, studio: dict, auth: AuthHeaders, use_provider, engine: Engine
) -> None:
    use_provider(FakeProvider([says("Hi."), says("Hi.")]))
    headers = studio["headers"]
    desk, other = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    add_member(engine, studio["tenant_id"], other, "front_desk")

    saved = client.put(
        "/ai/spend/limits",
        json={"limits": [{"kind": "role", "key": "front_desk", "monthly_credits": 50}]},
        headers=headers,
    ).json()
    assert saved["limits"] == [{"kind": "role", "key": "front_desk", "monthly_credits": 50}]

    spend_credits(engine, 60, user_id=str(desk))  # the plan is fine, this person is over
    desk_headers = auth(desk, studio["tenant_id"])
    blocked = ask(client, desk_headers, conversation(client, desk_headers), "hi")
    assert blocked.status_code == 409 and blocked.json()["detail"] == "ai_user_limit_reached"

    other_headers = auth(other, studio["tenant_id"])  # the role limit is per person
    assert ask(client, other_headers, conversation(client, other_headers), "hi").status_code == 200

    bad = client.put(
        "/ai/spend/limits",
        json={"limits": [{"kind": "user", "key": "nobody", "monthly_credits": 5}]},
        headers=headers,
    )
    assert bad.status_code == 422
    assert (
        client.put("/ai/spend/limits", json={"limits": []}, headers=headers).json()["limits"] == []
    )


def test_alerts_are_raised_once_per_threshold(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    use_provider(FakeProvider([says("Hi."), says("Hi."), says("Hi.")]))
    headers = studio["headers"]
    client.put("/ai/spend", json={"payg_enabled": True}, headers=headers)
    included = client.get("/ai/spend", headers=headers).json()["credits_included"]
    assert client.get("/ai/spend", headers=headers).json()["alerts"] == []

    spend_credits(engine, included * 0.85)
    ask(client, headers, conversation(client, headers), "hi")
    assert client.get("/ai/spend", headers=headers).json()["alerts"] == [80]

    spend_credits(engine, included * 0.7)  # 155% in total
    ask(client, headers, conversation(client, headers), "hi")
    ask(client, headers, conversation(client, headers), "hi")
    assert client.get("/ai/spend", headers=headers).json()["alerts"] == [80, 100, 150]


def test_the_agent_modules_are_open(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    catalog = client.get("/modules/catalog", headers=headers).json()["modules"]
    assert {"analytics_pro", "agent_finance", "agent_marketing"} <= {m["key"] for m in catalog}
    assert all(m["available"] for m in catalog)
    on = client.put(
        "/tenants/current/modules",
        json={"modules": {"ai_pro": 1, "crm": 1, "agent_finance": 1, "agent_marketing": 1}},
        headers=headers,
    )
    assert on.status_code == 200, on.text
