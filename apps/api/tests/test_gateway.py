import json

import anthropic
import httpx2

from app.ai.gateway import AnthropicProvider, Usage, credits


def test_anthropic_request_shape() -> None:
    """The provider sends the request we intend (model, effort, fallbacks, caching, strict
    tools) and maps the response back, without calling the real API."""
    seen: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["beta"] = request.headers.get("anthropic-beta")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": "Hi"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 0,
                },
            },
        )

    provider = AnthropicProvider("test-key", "claude-opus-5-5")
    provider.client = anthropic.Anthropic(
        api_key="test-key", http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    tool = {"name": "t", "description": "d", "strict": True, "input_schema": {"type": "object"}}

    response = provider.create("system", [{"role": "user", "content": "hello"}], [tool])

    body = seen["body"]
    assert seen["url"].endswith("/v1/messages?beta=true")
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "medium"}
    assert body["cache_control"] == {"type": "ephemeral"}
    assert body["tools"][0]["strict"] is True
    assert "thinking" not in body  # Opus 5.5 always thinks adaptively
    assert response.content == [{"type": "text", "text": "Hi"}]
    assert response.usage == Usage(10, 5, 100, 0)


def test_credits_are_cents_of_model_cost() -> None:
    # 1M input tokens of Opus 5.5 cost $4 = 400 credits.
    assert credits("claude-opus-5-5", Usage(input_tokens=1_000_000)) == 400
    assert credits("claude-opus-5-5", Usage(output_tokens=1_000)) == 2


def test_the_app_starts_without_loading_the_sdk() -> None:
    """Some locked-down Windows machines block the SDK's native extensions (jiter); without an
    API key the API must still start (demo mode), so the SDK is imported only when used."""
    import subprocess
    import sys

    check = "import sys, app.main; print('anthropic' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
