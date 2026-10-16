# ruff: noqa: F811, F401
"""Shira, the content agent: reads the studio's numbers, saves drafts and publishes only after
the owner confirms a card. Branch scope and permissions apply like for every other agent."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.providers.secrets import encrypt
from app.social import studio
from app.social.providers import Published
from tests.conftest import AuthHeaders
from tests.test_ai_agents import ask, chat, scope_agent, tool_names, tool_result
from tests.test_assistant import FakeProvider, calls, says, use_provider
from tests.test_branch_access import branches


def open_studio(client: TestClient, studio_fixture: dict) -> dict:
    owner = studio_fixture["headers"]
    response = client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_pro": 1, "social_studio": 1}},
        headers=owner,
    )
    assert response.status_code == 200, response.text
    assert client.post("/social/connect/demo", headers=owner).status_code == 201
    return owner


def accounts_of(client: TestClient, headers: dict) -> list[dict]:
    return client.get("/social/accounts", headers=headers).json()


def test_shira_gets_the_studio_tools_only_with_the_module(
    client: TestClient, studio: dict, use_provider
) -> None:
    owner = open_studio(client, studio)
    provider = FakeProvider([says("hi")])
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "hi")
    assert {
        "social_overview",
        "top_posts",
        "audience_summary",
        "draft_post",
        "list_drafts",
        "publish_post",
    } <= tool_names(provider)
    assert "get_metrics" not in tool_names(provider)  # no finance or client tools


def test_shira_reads_the_numbers_of_the_connected_accounts(
    client: TestClient, studio: dict, use_provider
) -> None:
    owner = open_studio(client, studio)
    provider = FakeProvider(
        [calls("social_overview", {"network": "", "days": 30}), says("Reels work best.")]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "What worked this month?")
    result = tool_result(provider)
    assert result["kpis"]["followers"]["value"] > 0
    assert result["best_times"] and result["accounts"]
    assert all(not a["can_publish"] for a in result["accounts"])  # demo accounts


def test_top_posts_and_audience(client: TestClient, studio: dict, use_provider) -> None:
    owner = open_studio(client, studio)
    provider = FakeProvider(
        [
            calls("top_posts", {"network": "tiktok", "days": 90, "sort": "views", "limit": 3}),
            calls("audience_summary", {"network": ""}),
            says("ok"),
        ]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "top posts")
    posts = tool_result(provider)["posts"]
    assert posts and len(posts) <= 3 and {p["network"] for p in posts} == {"tiktok"}
    audience = tool_result(provider, 2)["audience"]
    assert set(audience) >= {"age", "gender", "city"}
    assert all(len(group) <= 3 for group in audience.values())


def test_a_bad_network_is_an_error_the_model_can_read(
    client: TestClient, studio: dict, use_provider
) -> None:
    owner = open_studio(client, studio)
    provider = FakeProvider(
        [calls("social_overview", {"network": "myspace", "days": 7}), says("x")]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "numbers")
    assert "unknown network" in tool_result(provider)["error"]


def test_drafts_are_saved_listed_and_discarded(
    client: TestClient, studio: dict, use_provider
) -> None:
    owner = open_studio(client, studio)
    provider = FakeProvider(
        [
            calls(
                "draft_post",
                {
                    "network": "instagram",
                    "text": "Monday reset: 20 minutes of mobility.",
                    "image_url": "",
                    "idea": "Mobility reels did well",
                },
            ),
            calls("list_drafts", {}),
            says("Saved."),
        ]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "write a post")
    assert tool_result(provider)["saved"] is True
    [draft] = tool_result(provider, 2)["drafts"]
    assert draft["network"] == "instagram" and "mobility" in draft["text"].lower()

    listed = client.get("/social/drafts", headers=owner).json()
    assert [d["id"] for d in listed] == [draft["draft_id"]]
    assert client.delete(f"/social/drafts/{draft['draft_id']}", headers=owner).status_code == 204
    assert client.get("/social/drafts", headers=owner).json() == []
    assert client.delete(f"/social/drafts/{draft['draft_id']}", headers=owner).status_code == 404


def connect_fake_account(
    engine: Engine, tenant_id, monkeypatch: pytest.MonkeyPatch, location_id=None
) -> str:
    """A connected account whose network 'publishes' into a list, so no real network is hit."""
    published: list[tuple[str, str | None]] = []

    def publish(info, body, image_url):
        published.append((body, image_url))
        return Published("post-1", "https://example.com/p/1")

    fake = SimpleNamespace(name="fake", publish=publish)
    monkeypatch.setattr(studio, "social_provider", lambda name: fake if name == "fake" else None)
    account_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.social_accounts
                    (id, tenant_id, location_id, provider, network, external_id, name, secrets)
                VALUES (:id, :tenant, :location, 'fake', 'instagram', 'ig-1', 'Studio IG', :s)
            """),
            {
                "id": account_id,
                "tenant": tenant_id,
                "location": location_id,
                "s": encrypt({"token": "t"}),
            },
        )
    connect_fake_account.published = published  # type: ignore[attr-defined]
    return str(account_id)


def propose_publish(client, owner, use_provider, draft_id: str, account_id: str):
    provider = FakeProvider(
        [
            calls("publish_post", {"draft_id": draft_id, "account_id": account_id}),
            says("Please confirm."),
        ]
    )
    use_provider(provider)
    return ask(client, owner, chat(client, owner, "creative"), "publish it")


def new_draft(client, owner, use_provider) -> str:
    provider = FakeProvider(
        [
            calls(
                "draft_post",
                {"network": "instagram", "text": "Hello!", "image_url": "", "idea": ""},
            ),
            says("Saved."),
        ]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "draft")
    return client.get("/social/drafts", headers=owner).json()[0]["id"]


def test_publishing_waits_for_the_confirmation_card(
    client: TestClient,
    studio: dict,
    use_provider,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = open_studio(client, studio)
    account = connect_fake_account(engine, studio["tenant_id"], monkeypatch)
    draft = new_draft(client, owner, use_provider)

    turns = propose_publish(client, owner, use_provider, draft, account).json()["turns"]
    [card] = turns[-1]["pending_actions"]
    assert card["preview"]["kind"] == "publish_post" and card["preview"]["account"] == "Studio IG"
    assert connect_fake_account.published == []  # nothing before the owner taps

    done = client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=owner)
    assert done.status_code == 200 and done.json()["status"] == "executed"
    assert connect_fake_account.published == [("Hello!", None)]
    assert client.get("/social/drafts", headers=owner).json() == []  # the draft is now live
    again = client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=owner)
    assert again.status_code == 409
    with engine.connect() as connection:
        actions = connection.execute(text("SELECT action FROM app.audit_log")).scalars().all()
    assert "assistant.publish_post" in actions


def test_demo_and_unknown_accounts_cannot_be_published_to(
    client: TestClient, studio: dict, use_provider
) -> None:
    owner = open_studio(client, studio)
    draft = new_draft(client, owner, use_provider)
    demo = next(a["id"] for a in accounts_of(client, owner) if a["network"] == "instagram")
    provider = FakeProvider(
        [
            calls("publish_post", {"draft_id": draft, "account_id": demo}),
            calls("publish_post", {"draft_id": draft, "account_id": str(uuid4())}),
            says("no"),
        ]
    )
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "publish")
    assert "cannot publish" in tool_result(provider)["error"]
    assert "no such connected account" in tool_result(provider, 2)["error"]


def test_a_branch_limited_agent_only_sees_its_branch_accounts(
    client: TestClient,
    studio: dict,
    branches: dict,
    use_provider,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = branches["owner"]
    client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_pro": 1, "social_studio": 1}},
        headers=owner,
    )
    south = connect_fake_account(engine, studio["tenant_id"], monkeypatch, branches["south"])
    scope_agent(client, owner, "creative", [branches["north"]])
    provider = FakeProvider([calls("social_overview", {"network": "", "days": 30}), says("x")])
    use_provider(provider)
    ask(client, owner, chat(client, owner, "creative"), "numbers")
    result = tool_result(provider)
    assert result["accounts"] == []  # the only account belongs to the south branch
    assert south not in str(result)
