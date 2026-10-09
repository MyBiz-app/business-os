"""Modules: what a business turns on and pays for (spec 03 - pricing & configurator).

Prices are PLACEHOLDERS from the spec, for modelling only. Billing works on modules (line
items); presets are just recommended selections. The API enforces dependencies and gates
features by module, so the UI can never enable what the plan does not include."""

from dataclasses import dataclass, field
from typing import Literal

ModuleKey = Literal[
    "client_app",
    "client_app_branded",
    "ai_basic",
    "ai_pro",
    "crm",
    "crm_automation",
    "analytics_pro",
    "agent_finance",
    "agent_marketing",
    "whatsapp",
    "whatsapp_ai",
    "pack_plus",
    "pack_max",
    "support_priority",
    "support_vip",
    "setup_guided",
    "setup_full",
    "extra_location",
]
Billing = Literal["monthly", "once"]
PresetKey = Literal["starter", "growing", "ai_powered"]


@dataclass(frozen=True)
class Module:
    key: ModuleKey
    prices: dict[str, int]  # monthly, minor units, by currency
    requires_any: tuple[ModuleKey, ...] = ()  # at least one of these must be on
    requires_all: tuple[ModuleKey, ...] = ()
    available: bool = True  # False: shown as "coming soon", cannot be enabled
    per_unit: bool = False  # priced per unit (e.g. per extra location)
    group: str | None = None  # tiers of one thing (AI, support…): at most one per group
    billing: Billing = "monthly"  # "once": a service charged with the first invoice only


MODULES: dict[str, Module] = {
    m.key: m
    for m in (
        Module("client_app", {"ILS": 4900, "USD": 1500, "EUR": 1400}),
        # Pro tiers of the sign-up journey's offers (decision X16).
        Module(
            "client_app_branded",
            {"ILS": 9900, "USD": 2900, "EUR": 2700},
            requires_all=("client_app",),
        ),
        Module("ai_basic", {"ILS": 4900, "USD": 1500, "EUR": 1400}, group="ai"),
        Module("ai_pro", {"ILS": 11900, "USD": 3500, "EUR": 3200}, group="ai"),
        Module("crm", {"ILS": 3900, "USD": 1200, "EUR": 1100}),
        Module("crm_automation", {"ILS": 3900, "USD": 1200, "EUR": 1100}, requires_all=("crm",)),
        Module("analytics_pro", {"ILS": 3900, "USD": 1200, "EUR": 1100}, available=False),
        Module(
            "agent_finance",
            {"ILS": 6900, "USD": 2000, "EUR": 1900},
            requires_any=("ai_basic", "ai_pro"),
            available=False,
        ),
        Module(
            "agent_marketing",
            {"ILS": 6900, "USD": 2000, "EUR": 1900},
            requires_any=("ai_basic", "ai_pro"),
            requires_all=("crm",),
            available=False,
        ),
        Module("whatsapp", {"ILS": 2900, "USD": 900, "EUR": 800}),
        Module(
            "whatsapp_ai",
            {"ILS": 5900, "USD": 1800, "EUR": 1600},
            requires_any=("ai_basic", "ai_pro"),
            requires_all=("whatsapp",),
        ),
        # More storage and messages than the core includes ("extra luggage").
        Module("pack_plus", {"ILS": 2900, "USD": 900, "EUR": 800}, group="pack"),
        Module("pack_max", {"ILS": 6900, "USD": 2000, "EUR": 1900}, group="pack"),
        # Support beyond the standard (email, next business day) that every plan has.
        Module("support_priority", {"ILS": 3900, "USD": 1200, "EUR": 1100}, group="support"),
        Module("support_vip", {"ILS": 14900, "USD": 4500, "EUR": 4100}, group="support"),
        # Setting the business up, by the MyBiz team: one-time services.
        Module(
            "setup_guided", {"ILS": 24900, "USD": 7500, "EUR": 6900}, group="setup", billing="once"
        ),
        Module(
            "setup_full", {"ILS": 69000, "USD": 19900, "EUR": 18500}, group="setup", billing="once"
        ),
        Module("extra_location", {"ILS": 2900, "USD": 900, "EUR": 800}, per_unit=True),
    )
}

# What a business may use each month: the included amounts, or a bigger bundle's (#104).
GB = 1024**3


@dataclass(frozen=True)
class Allowance:
    storage_bytes: int
    messages: int


ALLOWANCES: dict[str | None, Allowance] = {
    None: Allowance(storage_bytes=2 * GB, messages=200),
    "pack_plus": Allowance(storage_bytes=20 * GB, messages=1000),
    "pack_max": Allowance(storage_bytes=100 * GB, messages=5000),
}


def allowance(modules: "dict[str, int] | list[str]") -> tuple[str | None, Allowance]:
    """The business's bundle (None: the included one) and what it allows."""
    pack = next((key for key in ("pack_max", "pack_plus") if key in modules), None)
    return pack, ALLOWANCES[pack]


# Core is required and priced by the number of active clients (the price floor).
CORE_TIERS: tuple[tuple[int | None, dict[str, int]], ...] = (
    (100, {"ILS": 9900, "USD": 2900, "EUR": 2700}),
    (300, {"ILS": 14900, "USD": 4500, "EUR": 4100}),
    (1000, {"ILS": 24900, "USD": 7500, "EUR": 6900}),
    (None, {"ILS": 24900, "USD": 7500, "EUR": 6900}),  # 1,000+: custom; shown as a floor
)

PRESETS: dict[str, tuple[ModuleKey, ...]] = {
    "starter": (),
    "growing": ("client_app", "ai_basic"),
    "ai_powered": ("client_app", "ai_pro"),
}


@dataclass(frozen=True)
class Questionnaire:
    active_clients: int
    staff: int
    locations: int
    wants_client_app: bool
    wants_ai_actions: bool


@dataclass
class Quote:
    currency: str
    core: int
    core_tier: int | None  # upper bound of the active-clients tier; None = 1,000+
    lines: dict[str, int] = field(default_factory=dict)  # module -> monthly price
    once: dict[str, int] = field(default_factory=dict)  # one-time services -> price

    @property
    def total(self) -> int:
        return self.core + sum(self.lines.values())


def recommend(answers: Questionnaire) -> PresetKey:
    if answers.wants_ai_actions:
        return "ai_powered"
    if answers.wants_client_app or answers.active_clients > 100 or answers.staff > 3:
        return "growing"
    return "starter"


def validate(selection: dict[str, int]) -> str | None:
    """Returns an error code, or None if the selection can be enabled."""
    for key, quantity in selection.items():
        module = MODULES.get(key)
        if module is None:
            return "unknown_module"
        if not module.available:
            return "module_not_available"
        if quantity < 1 or (quantity > 1 and not module.per_unit) or quantity > 50:
            return "invalid_quantity"
        if module.requires_any and not any(r in selection for r in module.requires_any):
            return "missing_dependency"
        if any(r not in selection for r in module.requires_all):
            return "missing_dependency"
    groups = [MODULES[key].group for key in selection if MODULES[key].group]
    if len(groups) != len(set(groups)):
        return "choose_one_ai_tier" if groups.count("ai") > 1 else "choose_one_tier"
    return None


def quote(selection: dict[str, int], active_clients: int, currency: str) -> Quote:
    for limit, prices in CORE_TIERS:
        if limit is None or active_clients <= limit:
            core, tier = prices.get(currency, prices["USD"]), limit
            break
    result = Quote(currency=currency, core=core, core_tier=tier)
    for key, quantity in selection.items():
        module = MODULES[key]
        price = module.prices.get(currency, module.prices["USD"]) * quantity
        (result.once if module.billing == "once" else result.lines)[key] = price
    return result
