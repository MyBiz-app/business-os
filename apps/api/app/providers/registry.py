"""The registry of providers per capability, and the settings each provider declares."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

Capability = Literal["payments", "invoicing", "messaging", "email", "ai", "storage"]
CAPABILITIES: tuple[Capability, ...] = (
    "payments",
    "invoicing",
    "messaging",
    "email",
    "ai",
    "storage",
)
# Capabilities where each business connects its own account (its terminal, its invoicing
# account, its WhatsApp number); the others are the platform's.
PER_BUSINESS: tuple[Capability, ...] = ("payments", "invoicing", "messaging")


@dataclass(frozen=True)
class SettingField:
    """One setting a provider needs (an API key, a terminal number…)."""

    key: str
    label: str  # English; the screens show it as is (vendor terms are not translated)
    secret: bool = False
    required: bool = True


@dataclass(frozen=True)
class ProviderInfo:
    capability: Capability
    name: str
    label: str
    factory: Callable[[dict[str, str]], Any]
    fields: tuple[SettingField, ...] = ()
    builtin: bool = False  # works with no account (simulated, internal, log…)
    description: str = ""


@dataclass
class Registry:
    providers: dict[tuple[Capability, str], ProviderInfo] = field(default_factory=dict)

    def add(self, info: ProviderInfo) -> None:
        key = (info.capability, info.name)
        if key in self.providers:
            raise ValueError(f"provider registered twice: {info.capability}/{info.name}")
        self.providers[key] = info

    def get(self, capability: Capability, name: str) -> ProviderInfo:
        try:
            return self.providers[(capability, name)]
        except KeyError as error:
            raise UnknownProvider(f"{capability}/{name}") from error

    def of(self, capability: Capability) -> list[ProviderInfo]:
        return [p for (c, _), p in sorted(self.providers.items()) if c == capability]


class UnknownProvider(LookupError):
    """No provider with that name for that capability."""


class ProviderNotConfigured(RuntimeError):
    """A provider is missing a required setting."""


REGISTRY = Registry()


def register(
    capability: Capability,
    name: str,
    label: str,
    *,
    fields: tuple[SettingField, ...] = (),
    builtin: bool = False,
    description: str = "",
) -> Callable[[type], type]:
    """Class decorator: registers a provider. The class is built with its settings dict."""

    def decorate(cls: type) -> type:
        REGISTRY.add(
            ProviderInfo(
                capability=capability,
                name=name,
                label=label,
                factory=cls,
                fields=fields,
                builtin=builtin,
                description=description,
            )
        )
        return cls

    return decorate


def check_settings(info: ProviderInfo, values: dict[str, str]) -> dict[str, str]:
    """Only the provider's own settings, every required one present."""
    known = {f.key for f in info.fields}
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
    missing = [f.key for f in info.fields if f.required and not str(values.get(f.key, "")).strip()]
    if missing:
        raise ProviderNotConfigured(f"missing settings: {', '.join(missing)}")
    return {k: str(v).strip() for k, v in values.items() if str(v).strip()}
