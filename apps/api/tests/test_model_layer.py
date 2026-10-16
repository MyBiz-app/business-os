import json
from typing import Any

import httpx2
import pytest

from app.ai import models
from app.ai.gateway import (
    FallbackProvider,
    LLMResponse,
    ProviderBusy,
    ProviderUnavailable,
    Usage,
    clean_response,
    credits,
    stream_response,
)
from app.ai.vendors import GeminiProvider, OpenAIProvider, VendorDisabled

TOOLS = [
    {
        "name": "get_metrics",
        "description": "Metrics",
        "input_schema": {
            "type": "object",
            "properties": {"metric": {"type": "string"}},
            "additionalProperties": False,
        },
    }
]
HISTORY = [
    {"role": "user", "content": [{"type": "text", "text": "Revenue?"}]},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Checking."},
            {"type": "tool_use", "id": "t1", "name": "get_metrics", "input": {"metric": "rev"}},
        ],
    },
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]},
]


@pytest.fixture
def vendors_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "ENABLED_VENDORS", frozenset({"anthropic", "openai", "gemini"}))


def test_every_tier_has_an_anthropic_model_and_prices_follow_the_registry() -> None:
    assert [models.model_for_tier(t) for t in models.TIERS] == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]
    usage = Usage(input_tokens=1_000_000)
    assert credits("claude-haiku-5-5", usage) < credits("claude-sonnet-5-5", usage)
    assert credits("some-unknown-model", usage) == credits("claude-opus-5-5", usage)
    assert models.model_for_tier("standard", "openai") == "gpt-5"
    assert models.model_for_tier("strong", "openai") == "gpt-5"  # best lower tier


def test_clean_text_replaces_long_and_medium_dashes() -> None:
    assert models.clean_text("a — b") == "a - b"
    assert models.clean_text("a—b – c") == "a - b - c"
    assert models.clean_text("nothing here, 5-6") == "nothing here, 5-6"


def test_responses_are_cleaned_but_tool_calls_are_untouched() -> None:
    response = LLMResponse(
        [
            {"type": "text", "text": "Yes — done"},
            {"type": "tool_use", "id": "x", "name": "n", "input": {"q": "a—b"}},
        ],
        "tool_use",
        "m",
    )
    cleaned = clean_response(response)
    assert cleaned.content[0]["text"] == "Yes - done"
    assert cleaned.content[1]["input"] == {"q": "a—b"}


def test_vendor_adapters_are_disabled_by_default() -> None:
    with pytest.raises(VendorDisabled):
        OpenAIProvider("k", "gpt-5")
    with pytest.raises(VendorDisabled):
        GeminiProvider("k", "gemini-2.5-pro")


def test_openai_adapter_translates_both_ways(vendors_on: None) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "model": "gpt-5",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "Ok — looking",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_metrics",
                                        "arguments": '{"metric":"a"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "prompt_tokens_details": {"cached_tokens": 40},
                },
            },
        )

    provider = OpenAIProvider(
        "k", "gpt-5", client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    response = provider.create("sys", HISTORY, TOOLS)

    wire = seen["body"]["messages"]
    assert [m["role"] for m in wire] == ["system", "user", "assistant", "tool"]
    assert wire[2]["tool_calls"][0]["function"]["arguments"] == '{"metric": "rev"}'
    assert wire[3]["tool_call_id"] == "t1"
    assert seen["body"]["tools"][0]["function"]["parameters"] == TOOLS[0]["input_schema"]
    assert seen["auth"] == "Bearer k"
    assert response.stop_reason == "tool_use"
    assert response.content[0]["text"] == "Ok - looking"
    assert response.content[1] == {
        "type": "tool_use",
        "id": "c1",
        "name": "get_metrics",
        "input": {"metric": "a"},
    }
    assert response.usage == Usage(input_tokens=60, output_tokens=20, cache_read_tokens=40)


def test_gemini_adapter_translates_both_ways(vendors_on: None) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Done — here"}]},
                    }
                ],
                "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 7},
            },
        )

    provider = GeminiProvider(
        "k", "gemini-2.5-pro", client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    response = provider.create("sys", HISTORY, TOOLS)

    contents = seen["body"]["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "get_metrics"
    declaration = seen["body"]["tools"][0]["functionDeclarations"][0]
    assert "additionalProperties" not in declaration["parameters"]
    assert "gemini-2.5-pro:generateContent" in seen["url"]
    assert response.content == [{"type": "text", "text": "Done - here"}]
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 50


def test_vendor_errors_map_to_provider_errors(vendors_on: None) -> None:
    def make(status: int) -> OpenAIProvider:
        transport = httpx2.MockTransport(lambda _r: httpx2.Response(status, json={}))
        return OpenAIProvider("k", "gpt-5", client=httpx2.Client(transport=transport))

    with pytest.raises(ProviderBusy):
        make(429).create("s", HISTORY, [])
    with pytest.raises(ProviderUnavailable):
        make(500).create("s", HISTORY, [])


class Down:
    model = "down"

    def create(self, *_args: Any, **_kwargs: Any) -> LLMResponse:
        raise ProviderUnavailable


class Busy:
    model = "busy"

    def create(self, *_args: Any, **_kwargs: Any) -> LLMResponse:
        raise ProviderBusy


class Up:
    model = "up"

    def create(self, *_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse([{"type": "text", "text": "hi"}], "end_turn", "up")


def test_fallback_skips_unavailable_but_not_busy_providers() -> None:
    assert FallbackProvider([Down(), Up()]).create("s", [], []).model == "up"
    with pytest.raises(ProviderBusy):
        FallbackProvider([Busy(), Up()]).create("s", [], [])
    with pytest.raises(ProviderUnavailable):
        FallbackProvider([Down(), Down()]).create("s", [], [])


def test_providers_without_streaming_answer_in_one_piece() -> None:
    events = list(stream_response(Up(), "s", [], []))
    assert [e.kind for e in events] == ["text", "done"]
    assert events[0].text == "hi"
    assert events[1].response is not None
