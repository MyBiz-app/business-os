# ruff: noqa: F811, F401
"""The console agents' tools (slice C2): one business, system health, banners, churn, website
orders, the audit log and the signup funnel. Each tool reads through the same console function and
permission as its page, and the audit log is for owners only."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.ai.gateway import LLMResponse, Usage
from app.ai.untrusted import unwrap
from tests.conftest import AuthHeaders, make_staff
from tests.test_assistant import FakeProvider, says, use_provider

ALL = (
    "businesses.read",
    "businesses.act",
    "billing.manage",
    "inbox.manage",
    "usage.read",
    "incidents.manage",
)
NEW_TOOLS = {
    "business_detail",
    "system_health",
    "incident_banners",
    "churn",
    "website_orders",
    "audit_log",
    "signup_funnel",
}


def calls_all(*uses: tuple[str, dict]):
    """One model step that asks for several tools at once."""
    return lambda _messages: LLMResponse(
        content=[
            {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": args}
            for i, (name, args) in enumerate(uses)
        ],
        stop_reason="tool_use",
        model="claude-opus-5-5",
        usage=Usage(input_tokens=100, output_tokens=20),
    )


def asking(client: TestClient, engine: Engine, auth: AuthHeaders, use_provider, steps, *, level):
    user = uuid4()
    make_staff(engine, user, level, ALL)
    headers = auth(user)
    provider = FakeProvider(steps)
    use_provider(provider)
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "manager"}, headers=headers
    ).json()
    reply = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "Go."},
        headers=headers,
    )
    assert reply.status_code == 200, reply.text
    return provider, headers


def test_the_audit_log_tool_is_offered_to_owners_only(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    offered = {}
    for level in ("owner", "manager"):
        provider, _ = asking(client, engine, auth, use_provider, [says("ok")], level=level)
        offered[level] = {t["name"] for t in provider.calls[0]["tools"]}
    assert offered["owner"] >= NEW_TOOLS
    assert NEW_TOOLS - {"audit_log"} <= offered["manager"]
    assert "audit_log" not in offered["manager"]


def test_the_new_tools_read_what_their_console_pages_show(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, use_provider
) -> None:
    user = uuid4()
    make_staff(engine, user, "owner", ALL)
    banner = client.post(
        "/platform/incidents",
        json={"kind": "incident", "content": {"en": {"title": "Slow bookings", "body": ""}}},
        headers=auth(user),
    )
    assert banner.status_code == 201, banner.text
    provider, _ = asking(
        client,
        engine,
        auth,
        use_provider,
        [
            calls_all(
                ("business_detail", {"id": str(studio["tenant_id"])}),
                ("business_detail", {"id": str(uuid4())}),
                ("business_detail", {"id": "not-a-uuid"}),
                ("system_health", {}),
                ("incident_banners", {}),
                ("churn", {"days": 90}),
                ("website_orders", {"stage": ""}),
                ("audit_log", {"limit": 5, "action": ""}),
                ("signup_funnel", {"days": 30}),
            ),
            says("Done."),
        ],
        level="owner",
    )
    results = provider.calls[1]["messages"][-1]["content"]
    by_id = {r["tool_use_id"]: r for r in results}

    def body(i: int) -> dict:
        return json.loads(unwrap(by_id[f"toolu_{i}"]["content"]))

    assert body(0)["id"] == str(studio["tenant_id"]) and body(0)["name"]
    assert body(1) == {"error": "no business with this id"}
    assert by_id["toolu_2"]["is_error"] is True
    assert "jobs" in body(3)
    assert (
        body(4)["open"] == 1 and body(4)["banners"][0]["content"]["en"]["title"] == "Slow bookings"
    )
    assert {"total", "by_reason", "recent", "months"} <= body(5).keys()
    assert body(6) == {"total": 0, "orders": []}
    assert isinstance(body(7)["entries"], list)
    assert body(8)["days"] == 30
    assert not any(r.get("is_error") for i, r in by_id.items() if i != "toolu_2")


def test_a_tool_the_member_lacks_the_permission_for_is_refused(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    user = uuid4()
    make_staff(engine, user, "employee", ("businesses.read",))
    provider = FakeProvider([calls_all(("churn", {"days": 30}), ("audit_log", {})), says("No.")])
    use_provider(provider)
    headers = auth(user)
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "manager"}, headers=headers
    ).json()
    client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "Go."},
        headers=headers,
    )
    results = provider.calls[1]["messages"][-1]["content"]
    assert all(r["is_error"] and "not available" in unwrap(r["content"]) for r in results)
