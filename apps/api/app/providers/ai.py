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
