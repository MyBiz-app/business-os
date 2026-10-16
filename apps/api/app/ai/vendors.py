"""Adapters for other model vendors (OpenAI, Gemini), disabled until a vendor is enabled in
app/ai/models.py (paid-provider policy). Each translates the canonical Messages-API blocks to
the vendor's wire format and back, so conversations stay vendor-neutral in the database."""

import json
from typing import Any

import httpx2

from app.ai.gateway import (
    LLMResponse,
    ProviderBusy,
    ProviderUnavailable,
    Usage,
    clean_response,
)
from app.ai.models import vendor_enabled


class VendorDisabled(RuntimeError):
    """The vendor's adapter exists but is not enabled."""


def _check_enabled(vendor: str) -> None:
    if not vendor_enabled(vendor):
        raise VendorDisabled(f"{vendor} is not enabled")


def _post(client: httpx2.Client, url: str, headers: dict[str, str], body: dict) -> dict:
    try:
        response = client.post(url, headers=headers, json=body)
    except httpx2.HTTPError as error:
        raise ProviderUnavailable from error
    if response.status_code == 429:
        raise ProviderBusy
    if response.status_code >= 400:
        raise ProviderUnavailable(f"HTTP {response.status_code}")
    return response.json()


def _blocks(content: Any) -> list[dict[str, Any]]:
    return [{"type": "text", "text": content}] if isinstance(content, str) else list(content)


class OpenAIProvider:
    """OpenAI chat completions. Disabled until "openai" is in ENABLED_VENDORS."""

    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model: str,
        strong_model: str | None = None,
        max_tokens: int = 4096,
        client: httpx2.Client | None = None,
    ) -> None:
        _check_enabled("openai")
        self.api_key = api_key
        self.model = model
        self.strong_model = strong_model or model
        self.max_tokens = max_tokens
        self.client = client or httpx2.Client(timeout=60.0)

    @staticmethod
    def to_wire(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        wire: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for message in messages:
            blocks = _blocks(message["content"])
            if message["role"] == "assistant":
                texts = [b["text"] for b in blocks if b.get("type") == "text"]
                calls = [
                    {
                        "id": b["id"],
                        "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                    }
                    for b in blocks
                    if b.get("type") == "tool_use"
                ]
                entry: dict[str, Any] = {"role": "assistant", "content": "\n".join(texts) or None}
                if calls:
                    entry["tool_calls"] = calls
                wire.append(entry)
                continue
            for block in blocks:
                if block.get("type") == "tool_result":
                    wire.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        }
                    )
            texts = [b["text"] for b in blocks if b.get("type") == "text"]
            if texts:
                wire.append({"role": "user", "content": "\n".join(texts)})
        return wire

    @staticmethod
    def from_wire(data: dict[str, Any]) -> LLMResponse:
        choice = data["choices"][0]
        message = choice["message"]
        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        for call in message.get("tool_calls") or []:
            content.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["function"]["name"],
                    "input": json.loads(call["function"]["arguments"] or "{}"),
                }
            )
        stop = {"tool_calls": "tool_use", "length": "max_tokens"}.get(
            choice.get("finish_reason"), "end_turn"
        )
        usage = data.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        return LLMResponse(
            content,
            stop,
            data.get("model", ""),
            Usage(
                input_tokens=usage.get("prompt_tokens", 0) - cached,
                output_tokens=usage.get("completion_tokens", 0),
                cache_read_tokens=cached,
            ),
        )

    def create(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.strong_model if strong else self.model,
            "messages": self.to_wire(system, messages),
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ]
        data = _post(self.client, self.URL, {"Authorization": f"Bearer {self.api_key}"}, body)
        return clean_response(self.from_wire(data))


class GeminiProvider:
    """Google Gemini generateContent. Disabled until "gemini" is in ENABLED_VENDORS."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        api_key: str,
        model: str,
        strong_model: str | None = None,
        max_tokens: int = 4096,
        client: httpx2.Client | None = None,
    ) -> None:
        _check_enabled("gemini")
        self.api_key = api_key
        self.model = model
        self.strong_model = strong_model or model
        self.max_tokens = max_tokens
        self.client = client or httpx2.Client(timeout=60.0)

    @staticmethod
    def to_wire(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        names: dict[str, str] = {}  # tool_use id -> function name (Gemini answers by name)
        contents: list[dict[str, Any]] = []
        for message in messages:
            parts: list[dict[str, Any]] = []
            for block in _blocks(message["content"]):
                kind = block.get("type")
                if kind == "text":
                    parts.append({"text": block["text"]})
                elif kind == "tool_use":
                    names[block["id"]] = block["name"]
                    parts.append({"functionCall": {"name": block["name"], "args": block["input"]}})
                elif kind == "tool_result":
                    parts.append(
                        {
                            "functionResponse": {
                                "name": names.get(block["tool_use_id"], "tool"),
                                "response": {"result": block["content"]},
                            }
                        }
                    )
            role = "model" if message["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": parts})
        return contents

    @staticmethod
    def from_wire(data: dict[str, Any]) -> LLMResponse:
        candidate = data["candidates"][0]
        content: list[dict[str, Any]] = []
        for index, part in enumerate(candidate.get("content", {}).get("parts", [])):
            if part.get("text"):
                content.append({"type": "text", "text": part["text"]})
            elif "functionCall" in part:
                call = part["functionCall"]
                content.append(
                    {
                        "type": "tool_use",
                        "id": f"call_{index}",
                        "name": call["name"],
                        "input": call.get("args") or {},
                    }
                )
        has_call = any(b["type"] == "tool_use" for b in content)
        stop = (
            "tool_use"
            if has_call
            else ("max_tokens" if candidate.get("finishReason") == "MAX_TOKENS" else "end_turn")
        )
        usage = data.get("usageMetadata") or {}
        cached = usage.get("cachedContentTokenCount", 0)
        return LLMResponse(
            content,
            stop,
            data.get("modelVersion", ""),
            Usage(
                input_tokens=usage.get("promptTokenCount", 0) - cached,
                output_tokens=usage.get("candidatesTokenCount", 0),
                cache_read_tokens=cached,
            ),
        )

    def create(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> LLMResponse:
        model = self.strong_model if strong else self.model
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self.to_wire(messages),
            "generationConfig": {"maxOutputTokens": self.max_tokens},
        }
        if tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": _gemini_schema(t["input_schema"]),
                        }
                        for t in tools
                    ]
                }
            ]
        data = _post(
            self.client, self.URL.format(model=model), {"x-goog-api-key": self.api_key}, body
        )
        return clean_response(self.from_wire(data))


def _gemini_schema(schema: Any) -> Any:
    """Gemini accepts an OpenAPI subset of JSON Schema: drop the keys it rejects."""
    if isinstance(schema, dict):
        return {
            key: _gemini_schema(value)
            for key, value in schema.items()
            if key not in {"additionalProperties", "$schema"}
        }
    if isinstance(schema, list):
        return [_gemini_schema(item) for item in schema]
    return schema
