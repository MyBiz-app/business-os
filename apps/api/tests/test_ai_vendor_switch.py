"""Provider choice by settings and the R19 simulation's money guards. No network, no cost."""

import pytest

from app.ai import live_sim, models
from app.ai.demo import DemoProvider
from app.ai.gateway import AnthropicProvider, get_provider
from app.ai.vendors import GeminiProvider, OpenAIProvider
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_is_anthropic_when_keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_ANTHROPIC_API_KEY", "k")
    assert isinstance(get_provider(), AnthropicProvider)


def test_other_vendor_stays_off_until_switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_AI_PROVIDER", "openai")
    monkeypatch.setenv("API_OPENAI_API_KEY", "k")
    assert isinstance(get_provider(), DemoProvider)  # key and provider set, vendor not enabled
    monkeypatch.setenv("API_AI_ENABLED_VENDORS", "openai")
    get_settings.cache_clear()
    provider = get_provider()
    assert isinstance(provider, OpenAIProvider) and provider.model == "gpt-5-mini"


def test_gemini_switch_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_AI_PROVIDER", "gemini")
    monkeypatch.setenv("API_GEMINI_API_KEY", "k")
    monkeypatch.setenv("API_AI_ENABLED_VENDORS", "gemini")
    assert isinstance(get_provider(), GeminiProvider)


def test_unknown_vendor_cannot_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_AI_ENABLED_VENDORS", "acme")
    assert models.enabled_vendors() == models.ENABLED_VENDORS


def test_simulation_on_demo_is_free_and_reports(capsys: pytest.CaptureFixture[str]) -> None:
    assert live_sim.main(["--questions", "6"]) == 0
    out = capsys.readouterr().out
    assert "Total credits: 0.00" in out and "| light |" in out


def test_simulation_refuses_a_paid_provider_without_the_owner_go(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_ANTHROPIC_API_KEY", "k")
    assert live_sim.main(["--approved"]) == 3  # flag alone is not enough
    assert live_sim.main([]) == 3
