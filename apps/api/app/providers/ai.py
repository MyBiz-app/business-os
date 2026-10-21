"""AI: the language-model providers in app/ai/gateway.py, registered like every other provider."""

from app.ai.demo import DemoProvider
from app.ai.gateway import AnthropicProvider, LLMProvider
from app.providers.registry import SettingField, register


@register("ai", "demo", "Demo answers (no AI account)", builtin=True)
class DemoAI:
    def __new__(cls, settings: dict[str, str]) -> LLMProvider:  # type: ignore[misc]
        return DemoProvider()


@register(
    "ai",
    "anthropic",
    "Claude (Anthropic)",
    fields=(
        SettingField("api_key", "API key", secret=True),
        SettingField("model", "Model", required=False),
    ),
)
class AnthropicAI:
    def __new__(cls, settings: dict[str, str]) -> LLMProvider:  # type: ignore[misc]
        return AnthropicProvider(settings["api_key"], settings.get("model") or "claude-opus-5-5")


@register(
    "ai",
    "openai",
    "OpenAI (off until switched on)",
    fields=(
        SettingField("api_key", "API key", secret=True),
        SettingField("model", "Model", required=False),
    ),
)
class OpenAIAI:
    def __new__(cls, settings: dict[str, str]) -> LLMProvider:  # type: ignore[misc]
        from app.ai.vendors import OpenAIProvider

        return OpenAIProvider(settings["api_key"], settings.get("model") or "gpt-5-mini")


@register(
    "ai",
    "gemini",
    "Gemini (off until switched on)",
    fields=(
        SettingField("api_key", "API key", secret=True),
        SettingField("model", "Model", required=False),
    ),
)
class GeminiAI:
    def __new__(cls, settings: dict[str, str]) -> LLMProvider:  # type: ignore[misc]
        from app.ai.vendors import GeminiProvider

        return GeminiProvider(settings["api_key"], settings.get("model") or "gemini-2.5-flash")
