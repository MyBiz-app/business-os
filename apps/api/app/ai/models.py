"""The model registry: every model the platform can call, its vendor, tier and price.

Business code asks for a tier (`fast`, `standard`, `strong`), never for a model name. The
registry says which model serves a tier and what it costs, so a vendor or model can be swapped
here (and in settings) without touching the assistant. Vendors other than Anthropic are
adapters that stay disabled until the business operates and has a key (paid-provider policy)."""

import re
from dataclasses import dataclass
from typing import Literal

from app.core.config import get_settings

Tier = Literal["fast", "standard", "strong"]
TIERS: tuple[Tier, ...] = ("fast", "standard", "strong")

# Vendors that may be called. The adapters for the others exist and are tested, but they are
# not reachable until a vendor is added here (a deliberate, reviewed change).
ENABLED_VENDORS: frozenset[str] = frozenset({"anthropic", "demo"})


@dataclass(frozen=True)
class ModelInfo:
    id: str
    vendor: Literal["anthropic", "openai", "gemini", "demo"]
    tier: Tier
    # USD per million tokens: input, output, cache read, cache write.
    prices: tuple[float, float, float, float]
    context_tokens: int
    supports_tools: bool = True


# Anthropic prices are the platform's real ones. OpenAI and Gemini rows are placeholders for
# the disabled adapters: check them against the vendor's price list before enabling.
MODELS: dict[str, ModelInfo] = {
    m.id: m
    for m in (
        ModelInfo("claude-haiku-5-5", "anthropic", "fast", (0.10, 0.50, 0.01, 0.125), 200_000),
        ModelInfo("claude-sonnet-5-5", "anthropic", "standard", (2.0, 10.0, 0.20, 2.5), 200_000),
        ModelInfo("claude-opus-5-5", "anthropic", "strong", (4.0, 20.0, 0.20, 5.0), 200_000),
        ModelInfo("gpt-5-mini", "openai", "fast", (0.25, 2.0, 0.025, 0.25), 400_000),
        ModelInfo("gpt-5", "openai", "standard", (1.25, 10.0, 0.125, 1.25), 400_000),
        ModelInfo("gemini-2.5-flash", "gemini", "fast", (0.30, 2.5, 0.03, 0.30), 1_000_000),
        ModelInfo("gemini-2.5-pro", "gemini", "standard", (1.25, 10.0, 0.31, 1.25), 1_000_000),
        ModelInfo("demo", "demo", "fast", (0.0, 0.0, 0.0, 0.0), 0, supports_tools=False),
    )
}

# Unknown models are priced as the dearest one, so a new model never looks free.
DEAREST = "claude-opus-5-5"


# Models the console chose for a tier (platform_ai_settings); refreshed from the database on
# requests, so every API process follows a change within one request.
OVERRIDES: dict[Tier, str] = {}


def set_overrides(fast: str | None, standard: str | None, strong: str | None) -> None:
    OVERRIDES.clear()
    for tier, model in (("fast", fast), ("standard", standard), ("strong", strong)):
        if model in MODELS and MODELS[model].vendor in ENABLED_VENDORS:
            OVERRIDES[tier] = model  # type: ignore[index]


def prices_of(model: str) -> tuple[float, float, float, float]:
    return MODELS.get(model, MODELS[DEAREST]).prices


def model_for_tier(tier: Tier, vendor: str = "anthropic") -> str:
    """The model that serves a tier. Anthropic's tiers come from settings (the console can
    change them); other vendors use the first registry entry of that tier."""
    if vendor == "anthropic":
        if tier in OVERRIDES:
            return OVERRIDES[tier]
        settings = get_settings()
        configured = {
            "fast": settings.ai_model,
            "standard": settings.ai_strong_model,
            "strong": settings.ai_top_model,
        }[tier]
        if configured in MODELS:
            return configured
    for info in MODELS.values():
        if info.vendor == vendor and info.tier == tier:
            return info.id
    # A vendor without that tier serves it with its best lower tier.
    lower = TIERS[: TIERS.index(tier)][::-1]
    for fallback in lower:
        for info in MODELS.values():
            if info.vendor == vendor and info.tier == fallback:
                return info.id
    raise LookupError(f"no {vendor} model for tier {tier}")


def vendor_enabled(vendor: str) -> bool:
    return vendor in ENABLED_VENDORS


_DASHES = re.compile(r"\s*[\u2013\u2014]\s*")


def clean_text(value: str) -> str:
    """Replaces long and medium dashes with a plain hyphen (product rule: no long dash in
    anything the user reads). Spaces around the dash are kept as one space each side."""
    return _DASHES.sub(" - ", value) if _DASHES.search(value) else value
