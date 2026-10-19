# ruff: noqa: F811, F401
"""The market researcher and web search for console agents (slice C4): web search is off by
default and limited per month, the researcher saves price comparisons with a source for every
price, and the server (not the model) marks where we are dearer than the cheapest competitor."""

import datetime as dt
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.gateway import LLMResponse, Usage
from app.commerce.modules import MODULES
from tests.conftest import AuthHeaders
from tests.test_assistant import FakeProvider, calls, says, use_provider
from tests.test_platform_ai import staff

TODAY = dt.date.today().isoformat()


class SearchingProvider(FakeProvider):
    """A provider that can run web searches on its side, like the Anthropic one."""

    supports_web_search = True


def searched(count: int):
    return lambda _messages: LLMResponse(
        content=[{"type": "text", "text": "Found it."}],
        stop_reason="end_turn",
        model="claude-opus-5-5",
        usage=Usage(input_tokens=1000, output_tokens=100, web_searches=count),
    )


def ask_market(client: TestClient, headers: dict, text_: str = "Compare") -> Any:
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "market"}, headers=headers
    )
    assert chat.status_code == 201, chat.text
    return client.post(
        f"/platform/ai/assistant/conversations/{chat.json()['id']}/messages",
        json={"text": text_},
        headers=headers,
    )


def row(**over: Any) -> dict[str, Any]:
    base = {
        "item": "crm",
        "competitor": "Arbox",
        "currency": "ILS",
        "price_minor": 2900,
        "source_url": "https://example.com/pricing",
        "checked_on": TODAY,
        "note": "",
    }
    return base | over


def test_web_search_is_off_until_the_team_switches_it_on(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    _, _, reader = staff(engine, auth, "usage.read")
    _, _, owner = staff(engine, auth, "usage.read", "billing.manage")
    state = client.get("/platform/ai/web-search", headers=reader).json()
    assert state["enabled"] is False and state["monthly_limit"] == 0
    assert (
        client.put(
            "/platform/ai/web-search", json={"enabled": True, "monthly_limit": 30}, headers=reader
        ).status_code
        == 403
    )
    too_many = client.put(
        "/platform/ai/web-search", json={"enabled": True, "monthly_limit": 5000}, headers=owner
    )
    assert too_many.status_code == 422
    on = client.put(
        "/platform/ai/web-search", json={"enabled": True, "monthly_limit": 30}, headers=owner
    ).json()
    assert on["enabled"] is True and on["monthly_limit"] == 30 and on["used_this_month"] == 0
    with engine.begin() as connection:
        logged = connection.execute(
            text("SELECT details FROM app.platform_audit WHERE action = 'ai.web_search'")
        ).scalar_one()
    assert logged == {"enabled": True, "monthly_limit": 30}


def test_the_search_tool_is_offered_only_with_budget_to_the_researcher(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, owner = staff(engine, auth, "usage.read", "billing.manage")

    def offered(provider: FakeProvider, role: str = "market") -> list[str]:
        use_provider(provider)
        chat = client.post(
            "/platform/ai/assistant/conversations", json={"role": role}, headers=owner
        ).json()
        reply = client.post(
            f"/platform/ai/assistant/conversations/{chat['id']}/messages",
            json={"text": "hi"},
            headers=owner,
        )
        assert reply.status_code == 200, reply.text
        return [t["name"] for t in provider.calls[0]["tools"]]

    assert "web_search" not in offered(SearchingProvider([says("a")]))  # off by default
    client.put("/platform/ai/web-search", json={"enabled": True, "monthly_limit": 3}, headers=owner)
    provider = SearchingProvider([says("b")])
    assert "web_search" in offered(provider)
    search = next(t for t in provider.calls[0]["tools"] if t["name"] == "web_search")
    assert search["max_uses"] == 3  # never more than the month has left
    assert "web_search" not in offered(FakeProvider([says("c")]))  # provider cannot run it
    assert "web_search" not in offered(SearchingProvider([says("d")]), role="manager")


def test_searches_are_counted_against_the_monthly_limit(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, owner = staff(engine, auth, "usage.read", "billing.manage")
    client.put("/platform/ai/web-search", json={"enabled": True, "monthly_limit": 5}, headers=owner)
    use_provider(SearchingProvider([searched(5)]))
    assert ask_market(client, owner).status_code == 200
    state = client.get("/platform/ai/web-search", headers=owner).json()
    assert state["used_this_month"] == 5
    provider = SearchingProvider([says("again")])
    use_provider(provider)
    assert ask_market(client, owner).status_code == 200
    assert "web_search" not in [t["name"] for t in provider.calls[0]["tools"]]  # used up


def test_a_market_report_marks_where_we_are_dearer_than_the_cheapest_competitor(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, reader = staff(engine, auth, "usage.read")
    ours = MODULES["crm"].prices["ILS"]
    rows = [
        row(price_minor=ours - 1000),  # cheaper than us
        row(competitor="Boostapp", price_minor=ours + 500),
        row(item="ai_basic", competitor="Lee", price_minor=MODULES["ai_basic"].prices["ILS"] + 1),
    ]
    provider = FakeProvider(
        [
            calls("our_prices", {}),
            calls(
                "save_market_report", {"title": "October", "summary": "We are fair.", "rows": rows}
            ),
            says("Saved."),
        ]
    )
    use_provider(provider)
    assert ask_market(client, reader).status_code == 200
    saved = provider.calls[2]["messages"][-1]["content"][0]
    assert "is_error" not in saved
    assert "crm (ILS): 25.6% above Arbox" in saved["content"]

    listed = client.get("/platform/ai/reports", headers=reader).json()
    assert [r["title"] for r in listed] == ["October"]
    report = client.get(f"/platform/ai/reports/{listed[0]['id']}", headers=reader).json()
    by_item = {c["item"]: c for c in report["body"]["comparison"]}
    assert by_item["crm"]["pricier"] is True and by_item["crm"]["cheapest_competitor"] == "Arbox"
    assert by_item["ai_basic"]["pricier"] is False
    assert all(p["source_url"].startswith("https://") for p in report["body"]["prices"])


def test_a_price_without_a_proper_source_is_refused(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, reader = staff(engine, auth, "usage.read")
    bad = [
        row(source_url="http://example.com"),
        row(item="made_up"),
        row(checked_on="2999-01-01"),
        row(price_minor=0),
    ]
    steps = [calls("save_market_report", {"title": "t", "summary": "s", "rows": [r]}) for r in bad]
    provider = FakeProvider([*steps, says("Could not save.")])
    use_provider(provider)
    assert ask_market(client, reader).status_code == 200
    results = [c["messages"][-1]["content"][0] for c in provider.calls[1:]]
    assert len(results) == 4 and all(r.get("is_error") for r in results)
    assert client.get("/platform/ai/reports", headers=reader).json() == []


def test_reports_need_the_console_permission(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, use_provider
) -> None:
    _, _, nobody = staff(engine, auth)
    assert client.get("/platform/ai/reports", headers=nobody).status_code == 403
    assert client.get("/platform/ai/reports", headers=studio["headers"]).status_code == 403
    assert client.get("/platform/ai/reports?limit=0", headers=nobody).status_code == 422
    # A business's own session cannot reach the table at all.
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL ROLE app_api"))
        denied = False
        try:
            connection.execute(text("SELECT count(*) FROM app.platform_ai_reports"))
        except Exception:
            denied = True
    assert denied
    # The researcher is not on the map for someone who cannot read usage.
    cards = client.get("/platform/ai/agents", headers=nobody).json()
    assert "market" not in [a["key"] for a in cards]
    _, _, reader = staff(engine, auth, "usage.read")
    market = next(
        a for a in client.get("/platform/ai/agents", headers=reader).json() if a["key"] == "market"
    )
    assert market["ready"] is True
