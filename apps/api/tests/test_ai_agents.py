# ruff: noqa: F811, F401
"""The AI team (round 5, A1): the agent catalog and its overrides, who may use which agent, the
branch scope that every tool honours, hand-offs and the usage per agent."""

import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import agents as agent_catalog
from app.ai.tools import BRANCH_BLIND, TOOL_DOMAINS, TOOLS
from app.ai.untrusted import unwrap
from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_assistant import FakeProvider, calls, enable_ai_pro, says, use_provider
from tests.test_bookings import new_client, new_session
from tests.test_branch_access import branches, member_at_north
from tests.test_workspace import PNG


def tool_names(provider: FakeProvider, call: int = 0) -> set[str]:
    return {tool["name"] for tool in provider.calls[call]["tools"]}


def chat(client: TestClient, headers: dict, agent: str = "chief", **extra: Any) -> str:
    created = client.post("/ai/conversations", json={"agent_key": agent, **extra}, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def ask(client: TestClient, headers: dict, conversation_id: str, question: str):
    return client.post(
        f"/ai/conversations/{conversation_id}/messages", json={"text": question}, headers=headers
    )


def tool_result(provider: FakeProvider, call: int = 1) -> dict[str, Any]:
    """The result of the first tool call, as the model got it on its next call."""
    block = provider.calls[call]["messages"][-1]["content"][0]
    return json.loads(unwrap(block["content"]))


def manager_headers(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, role: str = "manager"
) -> dict[str, str]:
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, role)
    return auth(member, studio["tenant_id"])


# --- the catalog and the tools ---------------------------------------------------------------


def test_each_screen_route_belongs_to_one_agent() -> None:
    """The bubble in the web app reads this map, so a route must not be claimed twice."""
    seen: dict[str, str] = {}
    for spec in agent_catalog.CATALOG.values():
        for route in spec.routes:
            assert route.startswith("/") and not route.endswith("/")
            assert route not in seen, f"{route} is listed for {seen[route]} and {spec.key}"
            seen[route] = spec.key
    # Screens added in round 7 are covered too.
    assert {"/files", "/migration", "/settings", "/quotes", "/time"} <= set(seen)


def test_every_tool_belongs_to_a_domain_and_agents_use_known_domains() -> None:
    assert set(TOOL_DOMAINS) == set(TOOLS)
    assert set(TOOL_DOMAINS.values()) <= set(agent_catalog.DOMAINS)
    assert set(TOOLS) >= BRANCH_BLIND
    for spec in agent_catalog.CATALOG.values():
        assert spec.domains <= set(agent_catalog.DOMAINS), spec.key
        assert {"he", "en"} <= set(spec.name), spec.key
    assert len(agent_catalog.CATALOG) == 9


def test_team_states_follow_modules_and_roles(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    owner = studio["headers"]

    # No AI module at all: everything is locked and points at AI Basic.
    off = client.put("/tenants/current/modules", json={"modules": {"client_app": 1}}, headers=owner)
    assert off.status_code == 200, off.text
    team = client.get("/ai/team", headers=owner).json()
    team_keys = list(agent_catalog.CATALOG)
    assert [a["key"] for a in team["agents"]] == team_keys
    assert {a["key"]: a["state"] for a in team["agents"]} == dict.fromkeys(team_keys, "locked")
    assert {a["upsell_module"] for a in team["agents"]} == {"ai_basic"}
    assert team["can_manage"] is True
    assert team["agents"][1]["name"] == "שירי"  # the studio is Hebrew

    enable_ai_pro(client, studio)
    team = {a["key"]: a for a in client.get("/ai/team", headers=owner).json()["agents"]}
    assert team["chief"]["state"] == "active"
    assert team["secretary"]["state"] == "active"
    assert team["marketing"]["state"] == "locked"
    assert team["marketing"]["upsell_module"] == "agent_marketing"
    assert team["creative"]["upsell_module"] == "social_studio"

    # Front desk: the people-facing agents are theirs, the managers' agents are not.
    desk = {
        a["key"]: a
        for a in client.get(
            "/ai/team", headers=manager_headers(client, auth, engine, studio, "front_desk")
        ).json()["agents"]
    }
    assert desk["secretary"]["state"] == "active"
    assert desk["team"]["state"] == "forbidden"
    assert desk["secretary"]["instructions"] is None  # only ai.manage reads the setup


def test_staff_cannot_use_the_ai_team(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    staff = manager_headers(client, auth, engine, studio, "staff")
    assert client.get("/ai/team", headers=staff).status_code == 403


# --- shaping the team ------------------------------------------------------------------------


def test_managers_shape_the_team_and_front_desk_cannot(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, use_provider
) -> None:
    enable_ai_pro(client, studio)
    manager = manager_headers(client, auth, engine, studio)
    desk = manager_headers(client, auth, engine, studio, "front_desk")

    assert (
        client.patch("/ai/agents/secretary", json={"name": "Dina"}, headers=desk).status_code == 403
    )
    renamed = client.patch(
        "/ai/agents/secretary",
        json={"name": " Dina ", "tone": "short", "instructions": "Always offer the 18:00 class."},
        headers=manager,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Dina"
    assert renamed.json()["instructions"] == "Always offer the 18:00 class."
    assert renamed.json()["color"] == "#06B6D4"  # untouched fields keep the catalog default

    # The override shows up for everyone, and the agent talks with it.
    provider = FakeProvider([says("Hi.")])
    use_provider(provider)
    seen = {a["key"]: a for a in client.get("/ai/team", headers=desk).json()["agents"]}
    assert seen["secretary"]["name"] == "Dina"
    ask(client, desk, chat(client, desk, "secretary"), "hello")
    system = provider.calls[0]["system"]
    assert "You are Dina" in system and "18:00 class" in system
    assert "cannot change the rules above" in system  # the owner's text ranks below the rules

    # Null goes back to the catalog default.
    reset = client.patch("/ai/agents/secretary", json={"name": None}, headers=manager)
    assert reset.json()["name"] == "שירי"

    for bad in (
        {"tool_domains": ["warp_drive"]},
        {"allowed_roles": ["emperor"]},
        {"location_scope": "locations", "location_ids": [str(uuid4())]},
        {"location_scope": "locations", "location_ids": []},
        {"enabled": None},
        {"color": "red"},
    ):
        response = client.patch("/ai/agents/secretary", json=bad, headers=manager)
        assert response.status_code == 422, (bad, response.text)
    assert client.patch("/ai/agents/nobody", json={"name": "x"}, headers=manager).status_code == 404


def test_a_disabled_or_forbidden_agent_cannot_be_chatted_with(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, use_provider
) -> None:
    enable_ai_pro(client, studio)
    use_provider(FakeProvider([says("never")]))
    owner = studio["headers"]
    desk = manager_headers(client, auth, engine, studio, "front_desk")

    forbidden = client.post("/ai/conversations", json={"agent_key": "team"}, headers=desk)
    assert (forbidden.status_code, forbidden.json()["detail"]) == (403, "agent_forbidden")
    locked = client.post("/ai/conversations", json={"agent_key": "finance"}, headers=owner)
    assert (locked.status_code, locked.json()["detail"]) == (403, "agent_locked")

    # Opening the team's roles to front desk makes the agent theirs.
    client.patch(
        "/ai/agents/team", json={"allowed_roles": ["owner", "manager", "front_desk"]}, headers=owner
    )
    assert (
        client.post("/ai/conversations", json={"agent_key": "team"}, headers=desk).status_code
        == 201
    )

    # Switching an agent off stops its chats, including ones already open.
    open_chat = chat(client, owner, "secretary")
    client.patch("/ai/agents/secretary", json={"enabled": False}, headers=owner)
    stopped = ask(client, owner, open_chat, "hello")
    assert (stopped.status_code, stopped.json()["detail"]) == (403, "agent_disabled")
    assert (
        client.post("/ai/conversations", json={"agent_key": "secretary"}, headers=owner).status_code
        == 403
    )


def test_custom_agents(client: TestClient, studio: dict, use_provider) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    made = client.post(
        "/ai/agents",
        json={
            "name": "Gal",
            "role_title": "Front-door host",
            "instructions": "Greet and look up members.",
            "tool_domains": ["clients"],
            "allowed_roles": ["owner", "manager", "front_desk"],
        },
        headers=owner,
    )
    assert made.status_code == 201, made.text
    card = made.json()
    assert card["builtin"] is False and card["state"] == "active"
    assert card["key"] == f"custom:{card['id']}"

    provider = FakeProvider([says("Welcome.")])
    use_provider(provider)
    ask(client, owner, chat(client, owner, card["key"]), "hi")
    # Only the clients domain: no schedule, no metrics, no hand-over tool.
    assert tool_names(provider) == {"find_clients", "get_client", "inactive_members"}

    no_domain = client.post("/ai/agents", json={"name": "Empty", "tool_domains": []}, headers=owner)
    assert no_domain.status_code == 422
    assert (
        client.post(
            "/ai/agents", json={"name": "Odd", "tool_domains": ["routing"]}, headers=owner
        ).status_code
        == 422
    )

    assert client.delete(f"/ai/agents/{card['id']}", headers=owner).status_code == 204
    assert client.delete("/ai/agents/chief", headers=owner).status_code == 409
    keys = [a["key"] for a in client.get("/ai/team", headers=owner).json()["agents"]]
    assert card["key"] not in keys


# --- the toolbox, tiers, hand-offs -----------------------------------------------------------


def test_each_agent_gets_only_its_toolbox(client: TestClient, studio: dict, use_provider) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]

    chief = FakeProvider([says("a")])
    use_provider(chief)
    ask(client, owner, chat(client, owner, "chief"), "hi")
    assert {"get_metrics", "find_clients", "list_sessions", "suggest_agent"} <= tool_names(chief)

    secretary = FakeProvider([says("a")])
    use_provider(secretary)
    ask(client, owner, chat(client, owner, "secretary"), "hi")
    names = tool_names(secretary)
    assert {"list_sessions", "book_client", "find_clients", "suggest_agent"} <= names
    assert "get_metrics" not in names and "open_balances" not in names


def test_the_model_asking_for_a_tool_outside_the_toolbox_is_refused(
    client: TestClient, studio: dict, use_provider
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    provider = FakeProvider([
        calls("get_metrics", {"metrics": ["revenue"], "start_date": "2026-09-01",
                              "end_date": "2026-09-30"}),
        says("I cannot."),
    ])  # fmt: skip
    use_provider(provider)

    ask(client, owner, chat(client, owner, "secretary"), "revenue?")

    assert tool_result(provider) == {"error": "this tool is not available to the user"}


def test_agents_choose_the_model_tier(client: TestClient, studio: dict, use_provider) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    fast, strong = FakeProvider([says("a")]), FakeProvider([says("a")])

    use_provider(fast)
    ask(client, owner, chat(client, owner, "chief"), "hi")
    client.patch("/ai/agents/chief", json={"model_tier": "standard"}, headers=owner)
    use_provider(strong)
    ask(client, owner, chat(client, owner, "chief"), "hi")

    assert fast.calls[0]["strong"] is False
    assert strong.calls[0]["strong"] is True


def test_suggest_agent_offers_a_hand_over_and_carries_the_context(
    client: TestClient, studio: dict, use_provider
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    provider = FakeProvider([
        calls("suggest_agent", {"agent_key": "secretary", "reason": "She books classes."}),
        says("Maya can take it from here."),
        calls("suggest_agent", {"agent_key": "finance", "reason": "Money."}),
        says("I will answer myself."),
    ])  # fmt: skip
    use_provider(provider)
    first = chat(client, owner, "chief")

    turns = ask(client, owner, first, "Book Dana into tonight's class").json()["turns"]

    [offer] = turns[-1]["suggestions"]
    assert offer == {"agent_key": "secretary", "reason": "She books classes."}
    # A locked agent cannot be offered: the model gets an error and answers itself.
    ask(client, owner, first, "And the invoice?")
    assert "not available" in tool_result(provider, 3)["error"]

    # Accepting the card: a new chat with Maya that remembers the exchange.
    follow = FakeProvider([says("Booked.")])
    use_provider(follow)
    handed = chat(client, owner, "secretary", handoff_from=first)
    ask(client, owner, handed, "yes please")
    context = follow.calls[0]["messages"][0]["content"][0]["text"]
    assert "Handed over from another agent" in context and "the invoice" in context


def test_conversations_belong_to_their_agent_and_can_be_archived(
    client: TestClient, studio: dict, use_provider
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    use_provider(FakeProvider([says("a"), says("b")]))
    with_chief, with_maya = chat(client, owner, "chief"), chat(client, owner, "secretary")
    ask(client, owner, with_chief, "Who is late today?")
    ask(client, owner, with_maya, "Free slots?")

    everything = client.get("/ai/conversations", headers=owner).json()
    assert {c["agent_key"] for c in everything} == {"chief", "secretary"}
    only_maya = client.get("/ai/conversations?agent=secretary", headers=owner).json()
    assert [(c["id"], c["title"]) for c in only_maya] == [(with_maya, "Free slots?")]

    archived = client.post(f"/ai/conversations/{with_maya}/archive", headers=owner)
    assert archived.status_code == 200
    assert client.get("/ai/conversations?agent=secretary", headers=owner).json() == []
    assert len(client.get("/ai/conversations?archived=true", headers=owner).json()) == 1


def test_usage_is_counted_per_agent_and_person(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    use_provider(FakeProvider([says("a"), says("b")]))
    ask(client, owner, chat(client, owner, "chief"), "hi")
    ask(client, owner, chat(client, owner, "secretary"), "hi")

    usage = client.get("/ai/usage", headers=owner).json()
    assert {row["key"] for row in usage["by_agent"]} == {"chief", "secretary"}
    assert usage["credits_used"] > 0 and usage["credits_included"] == 1200
    assert [row["key"] for row in usage["by_user"]] == [str(studio["owner"])]
    assert [row["key"] for row in usage["by_day"]] == [local_today().isoformat()]
    team = {a["key"]: a for a in client.get("/ai/team", headers=owner).json()["agents"]}
    assert team["secretary"]["credits_used_month"] > 0
    assert team["team"]["credits_used_month"] == 0


def test_proposed_actions_are_filed_under_the_agent(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, owner, "Dana")
    use_provider(FakeProvider([
        calls("book_client", {"session_id": session_id, "client_id": dana}),
        says("Confirm below."),
    ]))  # fmt: skip

    ask(client, owner, chat(client, owner, "secretary"), "Book Dana")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT agent_key FROM app.pending_actions")).scalar() == (
            "secretary"
        )


# --- branch scope ----------------------------------------------------------------------------


def scope_agent(client: TestClient, headers: dict, key: str, location_ids: list[str]) -> None:
    changed = client.patch(
        f"/ai/agents/{key}",
        json={"location_scope": "locations", "location_ids": location_ids},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["location_ids"] == sorted(location_ids)


def test_an_agent_scoped_to_one_branch_sees_only_that_branch(
    client: TestClient,
    studio: dict,
    branches: dict,
    use_provider,
) -> None:
    enable_ai_pro(client, studio)
    owner = branches["owner"]
    day = branches["day"]
    south = branches["south"]
    scope_agent(client, owner, "chief", [south])
    provider = FakeProvider([
        calls("list_sessions", {"start_date": day, "days": 1}),
        calls("find_clients", {"query": "north"}),
        calls("get_client", {"client_id": branches["north_client"]}),
        calls("get_session_roster", {"session_id": branches["north_session"]}),
        calls("get_metrics", {"metrics": ["new_clients"], "start_date": local_today().isoformat(),
                              "end_date": (local_today() + timedelta(days=1)).isoformat()}),
        calls("client_sources", {"start_date": local_today().isoformat(),
                                 "end_date": local_today().isoformat()}),
        says("done"),
    ])  # fmt: skip
    use_provider(provider)

    ask(client, owner, chat(client, owner, "chief"), "what do you see?")

    sessions = tool_result(provider, 1)["sessions"]
    assert [s["id"] for s in sessions] == [branches["south_session"]]
    assert tool_result(provider, 2)["clients"] == []  # the north client is not found by name
    assert tool_result(provider, 3) == {"error": "no client with that id"}
    assert "error" in tool_result(provider, 4)  # the north roster is not reachable
    metrics = tool_result(provider, 5)["metrics"]
    assert metrics[0]["value"] == 1  # only the south client counts as new
    assert [row["new_clients"] for row in tool_result(provider, 6)["sources"]] == [1]
    # The model is told which branches it sees.
    context = provider.calls[0]["messages"][0]["content"][0]["text"]
    assert '["South"]' in context

    # An agent without a scope (same owner) still sees both.
    both = FakeProvider([calls("list_sessions", {"start_date": day, "days": 1}), says("ok")])
    use_provider(both)
    ask(client, owner, chat(client, owner, "secretary"), "sessions")
    assert len(tool_result(both)["sessions"]) == 2


def test_the_scope_is_the_overlap_of_user_agent_and_chat(
    client: TestClient,
    studio: dict,
    branches: dict,
    auth: AuthHeaders,
    engine: Engine,
    use_provider,
) -> None:
    enable_ai_pro(client, studio)
    owner, day = branches["owner"], branches["day"]
    north, south = branches["north"], branches["south"]
    desk = member_at_north(client, auth, engine, studio, branches)

    def sessions_seen(headers: dict, agent: str, **extra: Any) -> list[str]:
        provider = FakeProvider(
            [calls("list_sessions", {"start_date": day, "days": 1}), says("ok")]
        )
        use_provider(provider)
        ask(client, headers, chat(client, headers, agent, **extra), "sessions")
        return [s["id"] for s in tool_result(provider)["sessions"]]

    # A branch-limited member: an unscoped agent still stops at their branch.
    assert sessions_seen(desk, "secretary") == [branches["north_session"]]

    # An agent scoped to the other branch leaves them nothing.
    scope_agent(client, owner, "secretary", [south])
    assert sessions_seen(desk, "secretary") == []

    # The owner narrows a chat of an unscoped agent to one branch; asking for a branch outside
    # a member's own is refused.
    assert sessions_seen(owner, "chief", location_ids=[north]) == [branches["north_session"]]
    outside = client.post(
        "/ai/conversations", json={"agent_key": "chief", "location_ids": [south]}, headers=desk
    )
    assert outside.status_code == 422

    # Agent and chat scopes intersect.
    scope_agent(client, owner, "secretary", [north, south])
    assert sessions_seen(owner, "secretary", location_ids=[south]) == [branches["south_session"]]


def test_tools_that_cannot_filter_by_branch_are_withheld_when_narrowed(
    client: TestClient,
    studio: dict,
    branches: dict,
    use_provider,
) -> None:
    enable_ai_pro(client, studio)
    owner = branches["owner"]
    client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_pro": 1, "crm": 1}},
        headers=owner,
    )
    wide = client.post(
        "/ai/agents", json={"name": "Wide", "tool_domains": ["leads", "clients"]}, headers=owner
    ).json()
    narrow = client.post(
        "/ai/agents",
        json={
            "name": "Narrow",
            "tool_domains": ["leads", "clients"],
            "location_scope": "locations",
            "location_ids": [branches["south"]],
        },
        headers=owner,
    ).json()
    unscoped, scoped = FakeProvider([says("a")]), FakeProvider([says("a")])

    use_provider(unscoped)
    ask(client, owner, chat(client, owner, wide["key"]), "leads?")
    use_provider(scoped)
    ask(client, owner, chat(client, owner, narrow["key"]), "leads?")

    assert "lead_pipeline" in tool_names(unscoped)
    assert "lead_pipeline" not in tool_names(scoped)
    assert "find_clients" in tool_names(scoped)


def test_groups_scope_fails_closed_until_branch_groups_exist() -> None:
    agent = agent_catalog.resolve(
        agent_catalog.CATALOG["chief"],
        None,
        "en",
    )
    from app.ai import scope

    grouped = agent_catalog.Agent(
        **{**agent.__dict__, "location_scope": "groups", "location_group_ids": frozenset({uuid4()})}
    )
    assert scope.agent_branches(None, grouped) == frozenset()  # type: ignore[arg-type]


# --- the new-agent wizard (A4): pictures, plan limits, the trial chat ---------------------------


def new_agent(client: TestClient, headers: dict, name: str = "Gal", **extra: Any):
    return client.post(
        "/ai/agents", json={"name": name, "tool_domains": ["clients"], **extra}, headers=headers
    )


def test_agent_pictures(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    card = new_agent(client, owner, avatar_preset="gallery-03").json()
    assert card["avatar_url"] is None

    uploaded = client.put(
        f"/ai/agents/{card['key']}/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=owner,
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["avatar_preset"] is None and body["avatar_url"].startswith(
        f"/ai/agents/{card['key']}/avatar?v="
    )
    served = client.get(body["avatar_url"], headers=owner)
    assert (served.status_code, served.content) == (200, PNG)
    assert served.headers["content-type"] == "image/png"

    # A built-in agent can have its own face too; choosing a gallery face drops the upload.
    chief = client.put(
        "/ai/agents/chief/avatar", files={"file": ("a.png", PNG, "image/png")}, headers=owner
    )
    assert chief.json()["avatar_url"]
    back = client.patch("/ai/agents/chief", json={"avatar_preset": "gallery-01"}, headers=owner)
    assert back.json()["avatar_url"] is None
    assert client.get("/ai/agents/chief/avatar", headers=owner).status_code == 404

    bad = client.put(
        f"/ai/agents/{card['key']}/avatar",
        files={"file": ("a.txt", b"nope", "text/plain")},
        headers=owner,
    )
    assert bad.status_code == 415
    removed = client.delete(f"/ai/agents/{card['key']}/avatar", headers=owner)
    assert removed.json()["avatar_url"] is None
    assert client.get(body["avatar_url"], headers=owner).status_code == 404

    desk = manager_headers(client, auth, engine, studio, "front_desk")
    assert (
        client.put(
            f"/ai/agents/{card['key']}/avatar",
            files={"file": ("a.png", PNG, "image/png")},
            headers=desk,
        ).status_code
        == 403
    )


def test_custom_agent_limit_follows_the_ai_module(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_basic": 1}},
        headers=owner,
    )
    for i in range(3):
        assert new_agent(client, owner, f"A{i}").status_code == 201
    team = client.get("/ai/team", headers=owner).json()
    assert (team["custom_count"], team["custom_limit"]) == (3, 3)
    full = new_agent(client, owner, "Four")
    assert (full.status_code, full.json()["detail"]) == (409, "agent_limit")

    enable_ai_pro(client, studio)
    assert client.get("/ai/team", headers=owner).json()["custom_limit"] == 10
    assert new_agent(client, owner, "Four").status_code == 201


def test_a_draft_agent_can_be_tried_before_it_joins_the_team(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, use_provider
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    desk = manager_headers(client, auth, engine, studio, "front_desk")
    draft = new_agent(client, owner, allowed_roles=["owner", "front_desk"], draft=True).json()

    team = client.get("/ai/team", headers=owner).json()
    assert draft["key"] not in [a["key"] for a in team["agents"]]
    assert team["custom_count"] == 1  # it already counts against the plan

    provider = FakeProvider([says("Hello, I am Gal.")])
    use_provider(provider)
    assert ask(client, owner, chat(client, owner, draft["key"]), "hi").status_code == 200
    assert (
        client.post("/ai/conversations", json={"agent_key": draft["key"]}, headers=desk).status_code
        == 403
    )

    saved = client.patch(f"/ai/agents/{draft['key']}", json={"draft": False}, headers=owner)
    assert saved.status_code == 200
    assert draft["key"] in [
        a["key"] for a in client.get("/ai/team", headers=owner).json()["agents"]
    ]
    assert (
        client.post("/ai/conversations", json={"agent_key": draft["key"]}, headers=desk).status_code
        == 201
    )
