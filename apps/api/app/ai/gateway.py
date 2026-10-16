"""LLM gateway: the only place that talks to a model provider.

Business code depends on `LLMProvider`, never on a provider SDK, so providers can be swapped
(and faked in tests). Every call reports token usage, which the assistant records as
`ai_credits` usage events."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ai.models import MODELS, clean_text, model_for_tier, prices_of
from app.core.config import get_settings


class ProviderBusy(Exception):
    """The provider is rate limiting us; try again shortly."""


class ProviderUnavailable(Exception):
    """The provider failed or could not be reached."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    # Content blocks as plain JSON (Messages API shape), stored and sent back unchanged.
    content: list[dict[str, Any]]
    stop_reason: str | None
    model: str
    usage: Usage = field(default_factory=Usage)


class LLMProvider(Protocol):
    model: str

    def create(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> LLMResponse:
        """One model call. `strong` asks for the stronger (dearer) model where the provider has
        one; a provider with a single model ignores it."""
        ...


# USD per million tokens: input, output, cache read, cache write (5-minute TTL), from the model
# registry (app/ai/models.py). Unknown models are priced as the dearest.
PRICES: dict[str, tuple[float, float, float, float]] = {m.id: m.prices for m in MODELS.values()}


def clean_response(response: LLMResponse) -> LLMResponse:
    """The response with long dashes removed from its text blocks (no long dash in anything the
    user reads, whatever the vendor wrote)."""
    content = [
        {**block, "text": clean_text(block["text"])}
        if block.get("type") == "text" and isinstance(block.get("text"), str)
        else block
        for block in response.content
    ]
    return LLMResponse(content, response.stop_reason, response.model, response.usage)


@dataclass(frozen=True)
class StreamEvent:
    """One piece of a streamed answer: `text` carries a text delta, `done` the final response."""

    kind: str  # "text" | "done"
    text: str = ""
    response: LLMResponse | None = None


def stream_response(
    provider: Any,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    strong: bool = False,
) -> Iterator[StreamEvent]:
    """Streams one model call. Providers with `create_stream` stream natively; the others
    (demo, test fakes) answer in one piece, so callers need no special case."""
    native = getattr(provider, "create_stream", None)
    if native is not None:
        yield from native(system, messages, tools, strong)
        return
    response = clean_response(provider.create(system, messages, tools, strong))
    for block in response.content:
        if block.get("type") == "text" and block.get("text"):
            yield StreamEvent("text", block["text"])
    yield StreamEvent("done", response=response)


def credits(model: str, usage: Usage) -> float:
    """AI credits for a call: one credit is one US cent of model cost. Owners see credits,
    never tokens (spec 03, usage meters)."""
    price_in, price_out, price_read, price_write = prices_of(model)
    dollars = (
        usage.input_tokens * price_in
        + usage.output_tokens * price_out
        + usage.cache_read_tokens * price_read
        + usage.cache_write_tokens * price_write
    ) / 1_000_000
    return round(dollars * 100, 4)


class AnthropicProvider:
    """Claude through the Anthropic API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        strong_model: str | None = None,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> None:
        # Imported here, not at module level: the SDK loads native extensions that some
        # locked-down Windows machines block, and it is only needed when a key is set.
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=timeout)
        self.model = model
        self.strong_model = strong_model or model
        self.max_tokens = max_tokens

    def create(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> LLMResponse:
        import anthropic

        try:
            response = self._call(
                system, messages, tools, self.strong_model if strong else self.model
            )
        except anthropic.RateLimitError as error:
            raise ProviderBusy from error
        except anthropic.APIError as error:
            raise ProviderUnavailable from error
        return clean_response(self._to_response(response))

    @staticmethod
    def _to_response(response: Any) -> LLMResponse:
        usage = response.usage
        content = [block.model_dump(mode="json", exclude_none=True) for block in response.content]
        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason,
            model=response.model,
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
            ),
        )

    def create_stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> Iterator[StreamEvent]:
        """Like `create`, but yields text deltas as they arrive, then the final response."""
        import anthropic

        model = self.strong_model if strong else self.model
        try:
            with self._call(system, messages, tools, model, stream=True) as stream:
                for delta in stream.text_stream:
                    yield StreamEvent("text", clean_text(delta))
                final = stream.get_final_message()
        except anthropic.RateLimitError as error:
            raise ProviderBusy from error
        except anthropic.APIError as error:
            raise ProviderUnavailable from error
        yield StreamEvent("done", response=clean_response(self._to_response(final)))

    def _call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        stream: bool = False,
    ) -> Any:
        extra: dict[str, Any] = {}
        if not model.startswith("claude-haiku"):
            # On a safety decline, the API retries on Anthropic's recommended model (Haiku has
            # no server-side fallback).
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        call = self.client.beta.messages.stream if stream else self.client.beta.messages.create
        return call(
            model=model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            # Business Q&A: medium effort is the model's default; stated explicitly.
            output_config={"effort": "medium"},
            # Cache the stable prefix (tools + system + history) between turns.
            cache_control={"type": "ephemeral"},
            **extra,
        )


def get_provider() -> LLMProvider | None:
    """The configured provider. Without an API key: demo mode when enabled (a prototype without
    paid services, decision T53), otherwise None (the assistant is not set up)."""
    settings = get_settings()
    if settings.anthropic_api_key is None:
        if settings.ai_demo:
            from app.ai.demo import DemoProvider

            return DemoProvider()
        return None
    return AnthropicProvider(
        settings.anthropic_api_key.get_secret_value(),
        model_for_tier("fast"),
        model_for_tier("standard"),
        settings.ai_max_tokens,
        settings.ai_timeout_seconds,
    )


class FallbackProvider:
    """Tries each provider in order when one is unavailable (not when it is merely busy: a busy
    provider is a rate limit on us, and trying another vendor would hide it). The first provider
    names the model for budget checks."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("at least one provider")
        self.providers = providers
        self.model = providers[0].model

    def create(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        strong: bool = False,
    ) -> LLMResponse:
        last: ProviderUnavailable | None = None
        for provider in self.providers:
            try:
                return provider.create(system, messages, tools, strong)
            except ProviderUnavailable as error:
                last = error
        raise ProviderUnavailable from last
