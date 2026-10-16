# ruff: noqa: F811, F401
"""The AI team structure (round 6, U3): reporting lines, teams, map positions and their meaning
for hand-overs."""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.ai import structure
from tests.conftest import AuthHeaders
from tests.test_ai_agents import ask, chat, manager_headers, new_agent
from tests.test_assistant import FakeProvider, calls, enable_ai_pro, says, use_provider


def save(client: TestClient, headers: dict, agents: list[dict[str, Any]], teams=()):
    return client.put(
        "/ai/structure", json={"teams": list(teams), "agents": agents}, headers=headers
    )


def card(client: TestClient, headers: dict, key: str) -> dict[str, Any]:
    return next(
        a for a in client.get("/ai/team", headers=headers).json()["agents"] if a["key"] == key
    )


def test_everyone_reports_to_the_chief_until_the_owner_changes_it(
    client: TestClient, studio: dict
) -> None:
    enable_ai_pro(client, studio)
    team = client.get("/ai/team", headers=studio["headers"]).json()
    assert team["teams"] == []
    parents = {a["key"]: a["reports_to"] for a in team["agents"]}
    assert parents["chief"] is None
    assert {v for k, v in parents.items() if k != "chief"} == {"chief"}


def test_lines_teams_and_positions_are_saved(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    team_id = str(uuid4())
    done = save(
        client,
        owner,
        [
            {
                "key": "secretary",
                "reports_to": "chief",
                "team_id": team_id,
                "map_x": 20,
                "map_y": 70,
            },
            {"key": "sales", "reports_to": "secretary", "team_id": team_id},
        ],
        teams=[{"id": team_id, "name": "Front desk", "color": "#2563EB", "lead_key": "secretary"}],
    )
    assert done.status_code == 200, done.text
    assert done.json()["teams"][0]["name"] == "Front desk"
    sales = card(client, owner, "sales")
    assert (sales["reports_to"], sales["team_id"]) == ("secretary", team_id)
    assert (
        card(client, owner, "secretary")["map_x"],
        card(client, owner, "secretary")["map_y"],
    ) == (20, 70)

    # Saving again without the team removes it and frees its members.
    save(client, owner, [{"key": "sales"}])
    assert client.get("/ai/team", headers=owner).json()["teams"] == []
    assert card(client, owner, "secretary")["team_id"] is None


def test_the_structure_rules(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]

    def error(agents: list[dict], teams=()) -> str:
        response = save(client, owner, agents, teams)
        assert response.status_code == 422, response.text
        return response.json()["detail"]

    assert error([{"key": "chief", "reports_to": "sales"}]) == "chief_on_top"
    assert error([{"key": "sales", "reports_to": "sales"}]) == "unknown_parent"
    assert error([{"key": "sales", "reports_to": "nobody"}]) == "unknown_parent"
    assert error([
        {"key": "sales", "reports_to": "secretary"},
        {"key": "secretary", "reports_to": "sales"},
    ]) == "cycle"  # fmt: skip
    assert error([{"key": "sales", "team_id": str(uuid4())}]) == "unknown_team"
    assert error([{"key": "nobody"}]) == "unknown_agent"
    team_id = str(uuid4())
    assert error(
        [{"key": "sales", "team_id": team_id}],
        [{"id": team_id, "name": "T", "lead_key": "secretary"}],
    ) == "lead_not_in_team"  # fmt: skip


def test_a_locked_agent_cannot_be_connected(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    locked = next(
        a for a in client.get("/ai/team", headers=owner).json()["agents"] if a["state"] == "locked"
    )
    response = save(client, owner, [{"key": locked["key"], "reports_to": "secretary"}])
    assert (response.status_code, response.json()["detail"]) == (422, "locked_agent")


def test_only_those_who_manage_the_team_shape_it(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    front = manager_headers(client, auth, engine, studio, role="front_desk")
    assert save(client, front, [{"key": "sales"}]).status_code == 403


def test_deleting_a_custom_agent_clears_the_lines_to_it(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    gal = new_agent(client, owner).json()
    save(client, owner, [{"key": "sales", "reports_to": gal["key"]}])
    assert card(client, owner, "sales")["reports_to"] == gal["key"]
    assert client.delete(f"/ai/agents/{gal['key']}", headers=owner).status_code == 204
    assert card(client, owner, "sales")["reports_to"] == "chief"


def test_a_hand_over_goes_to_the_team_lead_first(
    client: TestClient, studio: dict, use_provider
) -> None:
    enable_ai_pro(client, studio)
    owner = studio["headers"]
    team_id = str(uuid4())
    save(
        client,
        owner,
        [
            {"key": "secretary", "team_id": team_id},
            {"key": "sales", "team_id": team_id},
        ],
        teams=[{"id": team_id, "name": "Desk", "lead_key": "secretary"}],
    )
    provider = FakeProvider([
        calls("suggest_agent", {"agent_key": "sales", "reason": "A quote."}),
        says("Maya will take it."),
    ])  # fmt: skip
    use_provider(provider)
    turns = ask(client, owner, chat(client, owner, "chief"), "A member is unhappy").json()["turns"]
    [offer] = turns[-1]["suggestions"]
    assert offer["agent_key"] == "secretary"
    system = provider.calls[0]["system"]
    assert 'Team "Desk"' in system and "hand it to that team's lead first" in system


def test_structure_rules_in_isolation() -> None:
    keys = {"chief", "a", "b"}
    structure.check_structure(keys, {"a": "chief", "b": "a"}, set(), {}, {})
    try:
        structure.check_structure(keys, {"a": "b", "b": "a"}, set(), {}, {})
    except structure.StructureError as error:
        assert str(error) == "cycle"
    else:
        raise AssertionError("a cycle was accepted")
