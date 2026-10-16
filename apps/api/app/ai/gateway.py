"""LLM gateway: the only place that talks to a model provider.

Business code depends on `LLMProvider`, never on a provider SDK, so providers can be swapped
(and faked in tests). Every call reports token usage, which the assistant records as
`ai_credits` usage events."""

from dataclasses import dataclass, field
from typing import Any, Protocol

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


_LONG_DASHES = str.maketrans({"\u2014": "-", "\u2013": "-"})


def plain_dashes(text: str) -> str:
    """The product never shows an em or en dash: model output is normalised to a hyphen."""
    return text.translate(_LONG_DASHES)


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


# USD per million tokens: input, output, cache read, cache write (5-minute TTL).
# Haiku prices are for prompts up to 100K tokens; unknown models are priced as the dearest.
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}


def credits(model: str, usage: Usage) -> float:
    """AI credits for a call: one credit is one US cent of model cost. Owners see credits,
    never tokens (spec 03, usage meters)."""
    price_in, price_out, price_read, price_write = PRICES.get(model, PRICES["claude-opus-5-5"])
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
        usage = response.usage
        content = [block.model_dump(mode="json", exclude_none=True) for block in response.content]
        for block in content:
            if block.get("type") == "text":
                block["text"] = plain_dashes(block["text"])
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

    def _call(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str
    ) -> Any:
        extra: dict[str, Any] = {}
        if not model.startswith("claude-haiku"):
            # On a safety decline, the API retries on Anthropic's recommended model (Haiku has
            # no server-side fallback).
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        return self.client.beta.messages.create(
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
        settings.ai_model,
        settings.ai_strong_model,
        settings.ai_max_tokens,
        settings.ai_timeout_seconds,
    )
