# ruff: noqa: F811, F401
"""AI in the MyBiz console (round 5, A9): the cost board, model settings, the emergency stop,
pausing one business, and the console assistant's permissions and audit trail."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import models
from tests.conftest import AuthHeaders, make_staff
from tests.test_assistant import FakeProvider, ask, calls, conversation, says, use_provider


def staff(engine: Engine, auth: AuthHeaders, *permissions: str, level: str = "employee"):
    user = uuid4()
    email = make_staff(engine, user, level, tuple(permissions))
    return user, email, auth(user)


def audit_actions(engine: Engine) -> list[tuple[str, dict]]:
    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT action, details FROM app.platform_audit ORDER BY occurred_at")
        )
        return [(r.action, r.details) for r in rows]


def test_the_console_ai_routes_need_console_permissions(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    # A business owner is not on MyBiz's team.
    assert client.get("/platform/ai/costs", headers=studio["headers"]).status_code == 403
    assert client.get("/platform/ai/settings", headers=studio["headers"]).status_code == 403
    _, _, reader = staff(engine, auth, "usage.read")
    assert client.get("/platform/ai/costs", headers=reader).status_code == 200
    assert client.get("/platform/ai/settings", headers=reader).status_code == 200
    # Reading is not changing: the emergency stop and the pause need billing.manage.
    stop = client.put("/platform/ai/settings", json={"kill_all": True}, headers=reader)
    assert stop.status_code == 403
    pause = client.post(
        f"/platform/ai/businesses/{uuid4()}/pause",
        json={"paused": True, "reason": "abuse"},
        headers=reader,
    )
    assert pause.status_code == 403
    _, _, nobody = staff(engine, auth)
    assert client.get("/platform/ai/costs", headers=nobody).status_code == 403
    assert client.post("/platform/ai/assistant/conversations", headers=nobody).status_code == 201


def test_the_cost_board_sets_ai_cost_against_what_the_ai_modules_earn(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity)
                SELECT id, 'ai_credits', 250 FROM app.tenants
            """)
        )
    _, _, headers = staff(engine, auth, "usage.read")
    board = client.get("/platform/ai/costs?days=30", headers=headers).json()
    mine = next(b for b in board["businesses"] if b["tenant_id"] == str(studio["tenant_id"]))
    assert mine["credits"] >= 250 and mine["paused"] is False
    assert board["total_credits"] >= mine["credits"]
    assert client.get("/platform/ai/costs?days=0", headers=headers).status_code == 422


def test_models_are_chosen_per_tier_and_validated(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    _, _, headers = staff(engine, auth, "usage.read", "billing.manage")
    try:
        bad = client.put(
            "/platform/ai/settings",
            json={"kill_all": False, "model_fast": "gpt-5-mini"},
            headers=headers,
        )
        assert bad.status_code == 422 and bad.json()["detail"] == "model_not_available"
        wrong = client.put(
            "/platform/ai/settings",
            json={"kill_all": False, "model_fast": "claude-opus-5-5"},
            headers=headers,
        )
        assert wrong.status_code == 422 and wrong.json()["detail"] == "model_wrong_tier"
        ok = client.put(
            "/platform/ai/settings",
            json={"kill_all": False, "model_standard": "claude-sonnet-5-5"},
            headers=headers,
        )
        assert ok.status_code == 200 and ok.json()["model_standard"] == "claude-sonnet-5-5"
        assert models.model_for_tier("standard") == "claude-sonnet-5-5"
        assert any(action == "ai.settings" for action, _ in audit_actions(engine))
    finally:
        client.put("/platform/ai/settings", json={"kill_all": False}, headers=headers)
        models.set_overrides(None, None, None)


def test_the_emergency_stop_halts_every_business(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, use_provider
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    _, _, headers = staff(engine, auth, "usage.read", "billing.manage")
    owner = studio["headers"]
    client.put(
        "/tenants/current/modules", json={"modules": {"client_app": 1, "ai_pro": 1}}, headers=owner
    )
    try:
        stopped = client.put("/platform/ai/settings", json={"kill_all": True}, headers=headers)
        assert stopped.status_code == 200 and stopped.json()["kill_all"] is True
        refused = client.post("/ai/conversations", headers=owner)
        assert refused.status_code == 403 and refused.json()["detail"] == "ai_paused"
    finally:
        client.put("/platform/ai/settings", json={"kill_all": False}, headers=headers)
    assert client.post("/ai/conversations", headers=owner).status_code == 201


def test_one_business_can_be_paused_with_a_reason(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, use_provider
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    _, _, headers = staff(engine, auth, "usage.read", "billing.manage")
    owner = studio["headers"]
    client.put(
        "/tenants/current/modules", json={"modules": {"client_app": 1, "ai_pro": 1}}, headers=owner
    )
    url = f"/platform/ai/businesses/{studio['tenant_id']}/pause"
    assert client.post(url, json={"paused": True}, headers=headers).status_code == 422
    paused = client.post(url, json={"paused": True, "reason": "runaway loop"}, headers=headers)
    assert paused.status_code == 200
    assert [p["reason"] for p in paused.json()["pauses"]] == ["runaway loop"]
    assert client.post("/ai/conversations", headers=owner).status_code == 403
    board = client.get("/platform/ai/costs", headers=headers).json()
    assert next(b for b in board["businesses"] if b["tenant_id"] == str(studio["tenant_id"]))[
        "paused"
    ]

    resumed = client.post(url, json={"paused": False}, headers=headers)
    assert resumed.json()["pauses"] == []
    assert client.post("/ai/conversations", headers=owner).status_code == 201
    actions = [action for action, _ in audit_actions(engine)]
    assert "ai.paused" in actions and "ai.resumed" in actions


def test_a_business_cannot_read_or_change_the_console_ai_tables(
    engine: Engine, studio: dict
) -> None:
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL ROLE app_api"))
        for table in ("platform_ai_settings", "platform_ai_pauses"):
            try:
                with connection.begin_nested():
                    connection.execute(text(f"SELECT * FROM app.{table}"))
                reachable = True
            except Exception:
                reachable = False
            assert not reachable, table


def test_the_console_assistant_offers_only_tools_the_member_may_use(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    provider = FakeProvider(
        [
            calls("list_businesses", {"name": ""}),  # not offered: no businesses.read
            calls("open_requests", {}),
            says("Nothing urgent."),
        ]
    )
    use_provider(provider)
    _, _, headers = staff(engine, auth, "inbox.manage")
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "manager"}, headers=headers
    ).json()
    reply = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "What is open?"},
        headers=headers,
    )
    assert reply.status_code == 200, reply.text
    offered = [t["name"] for t in provider.calls[0]["tools"]]
    assert "open_requests" in offered and "list_businesses" not in offered
    refused = provider.calls[1]["messages"][-1]["content"][0]
    assert refused["is_error"] is True and "not available" in refused["content"]
    last = reply.json()["turns"][-1]
    assert last["role"] == "assistant" and last["text"].endswith("Nothing urgent.")
    assert reply.json()["credits"] > 0
    # The tool call was audited as the AI acting for the team member.
    logged = [d for a, d in audit_actions(engine) if a == "ai.tool.open_requests"]
    assert logged and logged[-1]["actor_type"] == "ai"


def test_console_conversations_are_private_and_staff_only(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, use_provider
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    _, _, mine = staff(engine, auth, "usage.read")
    _, _, theirs = staff(engine, auth, "usage.read")
    chat = client.post("/platform/ai/assistant/conversations", headers=mine).json()
    url = f"/platform/ai/assistant/conversations/{chat['id']}"
    assert client.get(url, headers=mine).status_code == 200
    assert client.get(url, headers=theirs).status_code == 404
    assert client.post(f"{url}/messages", json={"text": "hi"}, headers=theirs).status_code == 404
    # Not on MyBiz's team: no door at all.
    assert client.get(url, headers=studio["headers"]).status_code == 403
    assert (
        client.post("/platform/ai/assistant/conversations", headers=studio["headers"]).status_code
        == 403
    )


def test_the_emergency_stop_also_stops_the_console_assistant(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    use_provider(FakeProvider([says("Hi.")]))
    _, _, headers = staff(engine, auth, "usage.read", "billing.manage")
    chat = client.post("/platform/ai/assistant/conversations", headers=headers).json()
    try:
        client.put("/platform/ai/settings", json={"kill_all": True}, headers=headers)
        response = client.post(
            f"/platform/ai/assistant/conversations/{chat['id']}/messages",
            json={"text": "hi"},
            headers=headers,
        )
        assert response.status_code == 403 and response.json()["detail"] == "ai_paused"
    finally:
        client.put("/platform/ai/settings", json={"kill_all": False}, headers=headers)


def test_the_agents_map_shows_only_agents_the_member_may_ask(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    assert client.get("/platform/ai/agents", headers=studio["headers"]).status_code == 403
    _, _, nobody = staff(engine, auth)
    keys = [a["key"] for a in client.get("/platform/ai/agents", headers=nobody).json()]
    assert keys == ["manager"]  # the chief is for the whole team
    _, _, billing = staff(engine, auth, "billing.manage", "businesses.read")
    cards = client.get("/platform/ai/agents", headers=billing).json()
    keys = [a["key"] for a in cards]
    assert keys[0] == "manager" and "billing" in keys and "legal" in keys
    assert "support" not in keys and "security" not in keys  # needs inbox / incidents
    assert next(a for a in cards if a["key"] == "manager")["chief"] is True
    assert next(a for a in cards if a["key"] == "legal")["ready"] is True


def test_an_agent_can_be_renamed_switched_off_and_given_extra_instructions(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    provider = FakeProvider([says("Done.")])
    use_provider(provider)
    _, _, owner = staff(engine, auth, "billing.manage", "businesses.read")
    _, _, reader = staff(engine, auth, "businesses.read")
    change = {
        "enabled": True,
        "name_he": "Noa",
        "name_en": "Nora",
        "instructions": "We refund by card only.",
        "x": 20,
        "y": 30,
        "portrait_url": "https://example.com/nora.png",
    }
    assert client.put("/platform/ai/agents/billing", json=change, headers=reader).status_code == 403
    done = client.put("/platform/ai/agents/billing", json=change, headers=owner)
    assert done.status_code == 200, done.text
    card = next(a for a in done.json() if a["key"] == "billing")
    assert card["name_en"] == "Nora" and card["x"] == 20 and card["instructions"]
    # Extra instructions are shown only to someone who can change them.
    seen = client.get("/platform/ai/agents", headers=reader).json()
    assert all(a["instructions"] is None for a in seen)
    # They are always added to the agent's prompt.
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "billing"}, headers=owner
    ).json()
    sent = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "hi"},
        headers=owner,
    )
    assert sent.status_code == 200, sent.text
    assert "We refund by card only." in provider.calls[0]["system"]
    assert ("ai.agent", {"agent": "billing", "enabled": True, "has_instructions": True}) in (
        audit_actions(engine)
    )
    # Switched off: no new conversation, and the open one stops too. The chief cannot be off.
    off = {**change, "enabled": False}
    client.put("/platform/ai/agents/billing", json=off, headers=owner)
    again = client.post(
        "/platform/ai/assistant/conversations", json={"role": "billing"}, headers=owner
    )
    assert again.status_code == 409 and again.json()["detail"] == "agent_disabled"
    stopped = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "hi"},
        headers=owner,
    )
    assert stopped.status_code == 409
    client.put("/platform/ai/agents/manager", json=off, headers=owner)
    chief = next(a for a in client.get("/platform/ai/agents", headers=owner).json() if a["chief"])
    assert chief["enabled"] is True


def test_agents_without_permission_or_unknown_cannot_be_asked(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    _, _, owner = staff(engine, auth, "billing.manage")
    _, _, other = staff(engine, auth, "usage.read")
    denied = client.post(
        "/platform/ai/assistant/conversations", json={"role": "billing"}, headers=other
    )
    assert denied.status_code == 403
    unknown = client.post(
        "/platform/ai/assistant/conversations", json={"role": "nobody"}, headers=owner
    )
    assert unknown.status_code == 422


def test_product_success_and_marketing_agents_are_ready_with_their_own_tools(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    from app.ai.console import tools_for

    everything = frozenset(
        {"inbox.manage", "businesses.read", "billing.manage", "usage.read", "businesses.act"}
    )
    names = {
        role: {t.name for t in tools_for(role, everything)}
        for role in ("product", "success", "marketing")
    }
    assert {"open_requests", "churn", "signup_funnel", "industry_catalog"} <= names["product"]
    assert {"business_health", "business_detail", "churn", "open_requests"} <= names["success"]
    assert {"price_list", "industry_catalog", "signup_funnel"} <= names["marketing"]
    assert "price_list" not in names["product"] and "price_list" not in names["success"]
    assert "churn" not in names["marketing"] and "open_requests" not in names["marketing"]

    provider = FakeProvider([calls("price_list", {}), says("Draft: a landing page text.")])
    use_provider(provider)
    _, _, headers = staff(engine, auth, "inbox.manage")
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "marketing"}, headers=headers
    )
    assert chat.status_code == 201, chat.text
    reply = client.post(
        f"/platform/ai/assistant/conversations/{chat.json()['id']}/messages",
        json={"text": "Write landing page text"},
        headers=headers,
    )
    assert reply.status_code == 200, reply.text
    assert {t["name"] for t in provider.calls[0]["tools"]} == {
        "price_list",
        "industry_catalog",
        "search_library",
    }
    result = provider.calls[1]["messages"][-1]["content"][0]
    assert "core_by_active_clients" in result["content"] and not result.get("is_error")
    cards = client.get("/platform/ai/agents", headers=headers).json()
    ready = {a["key"]: a["ready"] for a in cards}
    assert ready["product"] and ready["marketing"]
    _, _, readers = staff(engine, auth, "businesses.read")
    cards = client.get("/platform/ai/agents", headers=readers).json()
    assert next(a for a in cards if a["key"] == "success")["ready"] is True
