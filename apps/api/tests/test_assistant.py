import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.gateway import LLMResponse, Usage, get_provider
from tests.conftest import AuthHeaders, add_member
from tests.test_bookings import new_client, new_session

Step = Callable[[list[dict[str, Any]]], LLMResponse]


class FakeProvider:
    """Plays scripted model turns and records what it was sent."""

    model = "claude-opus-5-5"

    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def create(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]):
        self.calls.append(
            {"system": system, "messages": json.loads(json.dumps(messages)), "tools": tools}
        )
        return self.steps.pop(0)(messages)


def says(answer: str) -> Step:
    return lambda _messages: LLMResponse(
        content=[{"type": "text", "text": answer}],
        stop_reason="end_turn",
        model="claude-opus-5-5",
        usage=Usage(input_tokens=1000, output_tokens=200),
    )


def calls(name: str, args: dict[str, Any]) -> Step:
    return lambda _messages: LLMResponse(
        content=[
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": f"toolu_{uuid4().hex[:8]}", "name": name, "input": args},
        ],
        stop_reason="tool_use",
        model="claude-opus-5-5",
        usage=Usage(input_tokens=1000, output_tokens=50, cache_read_tokens=3000),
    )


@pytest.fixture
def use_provider(client: TestClient):
    def install(provider: FakeProvider | None) -> None:
        client.app.dependency_overrides[get_provider] = lambda: provider  # type: ignore[attr-defined]

    yield install
    client.app.dependency_overrides.pop(get_provider, None)  # type: ignore[attr-defined]


def enable_ai_pro(client: TestClient, studio: dict) -> None:
    response = client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_pro": 1}},
        headers=studio["headers"],
    )
    assert response.status_code == 200, response.text


def conversation(client: TestClient, headers: dict) -> str:
    created = client.post("/ai/conversations", headers=headers)
    assert created.status_code == 201
    return created.json()["id"]


def ask(client: TestClient, headers: dict, conversation_id: str, question: str):
    return client.post(
        f"/ai/conversations/{conversation_id}/messages", json={"text": question}, headers=headers
    )


def test_not_configured_without_a_key(client: TestClient, studio: dict, use_provider) -> None:
    use_provider(None)
    headers = studio["headers"]

    assert client.get("/ai/status", headers=headers).json() == {"enabled": False}
    response = ask(client, headers, conversation(client, headers), "hi")
    assert response.status_code == 503
    assert response.json()["detail"] == "ai_not_configured"


def test_answers_with_metrics_and_records_usage(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    provider = FakeProvider([
        calls("get_metrics", {"metrics": ["revenue"], "start_date": "2026-09-01",
                              "end_date": "2026-09-30"}),
        says("Revenue in September was ₪0."),
    ])  # fmt: skip
    use_provider(provider)
    headers = studio["headers"]
    conversation_id = conversation(client, headers)

    response = ask(client, headers, conversation_id, "What was revenue in September?")

    assert response.status_code == 200, response.text
    turns = response.json()["turns"]
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["text"] == "What was revenue in September?"
    assert turns[1]["text"] == "Let me check.\n\nRevenue in September was ₪0."
    # The tool result went back to the model, and the context names the business.
    second = provider.calls[1]["messages"]
    tool_result = json.loads(second[-1]["content"][0]["content"])
    assert tool_result["metrics"][0]["metric"] == "revenue"
    assert "Studio Flow" in second[0]["content"][0]["text"]
    assert "Revenue" not in provider.calls[0]["system"]  # system prompt is static (cacheable)
    with engine.connect() as connection:
        events = connection.execute(
            text("SELECT meter, quantity FROM app.usage_events ORDER BY id")
        ).all()
    assert [e.meter for e in events] == ["ai_credits", "ai_credits"]
    assert all(e.quantity > 0 for e in events)


def test_booking_is_proposed_then_confirmed_once(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    use_provider(FakeProvider([
        calls("book_client", {"session_id": session_id, "client_id": dana}),
        says("I prepared the booking. Please confirm it below."),
    ]))  # fmt: skip
    conversation_id = conversation(client, headers)

    turns = ask(client, headers, conversation_id, "Book Dana into Pilates").json()["turns"]

    [card] = turns[-1]["pending_actions"]
    assert card["status"] == "pending"
    assert card["preview"]["client"] == "Dana"
    assert card["preview"]["service"] == "Pilates"
    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert roster == []  # nothing happens before confirmation

    confirmed = client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "executed"
    assert confirmed.json()["result"]["status"] == "booked"
    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert [b["client_name"] for b in roster] == ["Dana"]

    again = client.post(f"/ai/pending-actions/{card['id']}/confirm", headers=headers)
    assert again.status_code == 409
    with engine.connect() as connection:
        audit = connection.execute(text("SELECT actor_type, action FROM app.audit_log")).all()
    assert audit == [("ai", "assistant.book_client")]


def test_reject_expired_and_other_users(
    client: TestClient, studio: dict, use_provider, engine: Engine, auth: AuthHeaders
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    use_provider(FakeProvider([
        calls("book_client", {"session_id": session_id, "client_id": dana}),
        says("Confirm below."),
        calls("book_client", {"session_id": session_id, "client_id": dana}),
        says("Confirm below."),
    ]))  # fmt: skip
    conversation_id = conversation(client, headers)
    first = ask(client, headers, conversation_id, "Book Dana").json()["turns"][-1]
    second = ask(client, headers, conversation_id, "Book Dana again").json()["turns"][-1]
    first_id = first["pending_actions"][0]["id"]
    second_id = second["pending_actions"][0]["id"]

    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    manager_headers = auth(manager, studio["tenant_id"])
    assert (
        client.post(f"/ai/pending-actions/{first_id}/confirm", headers=manager_headers).status_code
        == 404
    )
    assert (
        client.get(f"/ai/conversations/{conversation_id}", headers=manager_headers).status_code
        == 404
    )

    rejected = client.post(f"/ai/pending-actions/{first_id}/reject", headers=headers)
    assert rejected.json()["status"] == "rejected"
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.pending_actions SET expires_at = now() - interval '1 minute' "
                "WHERE id = :id"
            ),
            {"id": second_id},
        )
    expired = client.post(f"/ai/pending-actions/{second_id}/confirm", headers=headers)
    assert expired.status_code == 409
    assert client.get(f"/sessions/{session_id}/bookings", headers=headers).json() == []


def test_tools_follow_the_users_permissions(
    client: TestClient, studio: dict, use_provider, engine: Engine, auth: AuthHeaders
) -> None:
    enable_ai_pro(client, studio)
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    provider = FakeProvider([
        calls("get_metrics", {"metrics": ["revenue"], "start_date": "2026-09-01",
                              "end_date": "2026-09-30"}),
        says("Sorry, I can't see revenue."),
    ])  # fmt: skip
    use_provider(provider)
    headers = auth(desk, studio["tenant_id"])

    ask(client, headers, conversation(client, headers), "Revenue?")

    offered = {tool["name"] for tool in provider.calls[0]["tools"]}
    assert "get_metrics" not in offered and "book_client" in offered
    result = provider.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    # Coaches (staff role) cannot use the assistant at all.
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.post("/ai/conversations", headers=coach).status_code == 403


def test_tool_errors_go_back_to_the_model(client: TestClient, studio: dict, use_provider) -> None:
    provider = FakeProvider([
        calls("get_client", {"client_id": "not-an-id"}),
        says("I couldn't find that client."),
    ])  # fmt: skip
    use_provider(provider)
    headers = studio["headers"]

    turns = ask(client, headers, conversation(client, headers), "Who is X?").json()["turns"]

    result = provider.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "not a valid id" in result["content"]
    assert turns[-1]["text"].endswith("I couldn't find that client.")
