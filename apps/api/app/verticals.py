"""Vertical packs: configuration that adapts the vertical-agnostic core to an industry.

Industries are categories and sub-categories in one catalog shared with the website and the
apps (packages/verticals). A sub-category inherits everything from its parent and overrides
only what it sets. The core never branches on the industry; it reads the resolved pack."""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DefaultPlan:
    """A plan every new business of the vertical starts with (editable afterwards)."""

    names: dict[str, str]  # by locale
    kind: str  # "membership" | "punch_card"
    validity_days: int
    prices: dict[str, int]  # minor units, by currency
    credits: int | None = None


@dataclass(frozen=True)
class DefaultService:
    """A service every new business of the vertical starts with (editable afterwards). For a
    resource (a court or room by the hour), duration_minutes is the shortest length and prices
    are per hour."""

    names: dict[str, str]  # by locale
    duration_minutes: int
    booking_mode: str  # "class" | "appointment" | "resource"
    prices: dict[str, int]  # minor units, by currency
    color: str
    capacity: int = 1
    max_minutes: int | None = None  # resource only
    step_minutes: int | None = None  # resource only
    on_site: bool = False  # appointment only: at the client's address (#42)
    travel_minutes: int = 0  # on-site: time to get there, before each job


@dataclass(frozen=True)
class DefaultRoom:
    """A court or room a new business starts with, in its main branch, for rent by the hour
    every day from `opens` to `closes`, serving the vertical's resource services."""

    names: dict[str, str]  # by locale
    opens: str  # "HH:MM", local
    closes: str
    capacity: int | None = None


@dataclass(frozen=True)
class ClientField:
    """An extra detail the vertical keeps about each client (labels: clientFields.<key>,
    select options: clientFields.<key>_options.<option>)."""

    key: str
    kind: str  # "text" | "long_text" | "number" | "date" | "select"
    options: tuple[str, ...] = ()
    max_length: int = 200


@dataclass(frozen=True)
class VerticalPack:
    """A catalog entry with everything it inherits from its parents filled in."""

    key: str
    status: str  # "live" | "beta" | "planned"
    parent: str | None
    category: str  # the top-level category (its own key for a category)
    terms: str  # the set of industry words in the translations (terms.<set>)
    client_term: str  # what the business calls its clients
    cancellation_window_minutes: int  # default booking policy for new businesses
    booking_requires_plan: bool  # clients need a valid plan to book in the client app
    default_preset: str  # modules a new business starts with (app/modules.py PRESETS)
    health_form: str | None = None  # app/health.py FORMS key clients sign before booking
    recommended_modules: tuple[str, ...] = ()
    default_plans: tuple[DefaultPlan, ...] = field(default_factory=tuple)
    default_services: tuple[DefaultService, ...] = field(default_factory=tuple)
    default_rooms: tuple[DefaultRoom, ...] = field(default_factory=tuple)
    # Dependents (#43): "pet" or "child" profiles under a client, their details, and whether
    # a booking must name one.
    dependents: str | None = None
    dependent_fields: tuple[ClientField, ...] = field(default_factory=tuple)
    dependent_required: bool = False
    time_billing: bool = False  # time entries, retainers and monthly bills (#45)
    client_fields: tuple[ClientField, ...] = field(default_factory=tuple)

    @property
    def requires_health_declaration(self) -> bool:
        return self.health_form is not None

    @property
    def is_open(self) -> bool:
        """A business can sign up with it."""
        return self.status != "planned"


# The industry catalog (packages/verticals/catalog/*.json), copied here by
# `pnpm verticals:export` because the API's image is built from apps/api alone.
CATALOG_PATH = Path(__file__).with_name("verticals_catalog.json")


def _prices(raw: dict[str, int]) -> dict[str, int]:
    """Prices by currency; USD and EUR default to rough equivalents of the ILS price."""
    usd = raw.get("USD", round(raw["ILS"] * 0.27 / 100) * 100)
    return {"ILS": raw["ILS"], "USD": usd, "EUR": raw.get("EUR", round(usd * 0.92 / 100) * 100)}


def _field(raw: dict[str, Any]) -> ClientField:
    return ClientField(
        raw["key"], raw["kind"], tuple(raw.get("options", ())), raw.get("max_length", 200)
    )


def _service(raw: dict[str, Any]) -> DefaultService:
    return DefaultService(
        names=raw["names"],
        duration_minutes=raw["duration_minutes"],
        booking_mode=raw["booking_mode"],
        prices=_prices(raw["prices"]),
        color=raw["color"],
        capacity=raw.get("capacity", 1),
        max_minutes=raw.get("max_minutes"),
        step_minutes=raw.get("step_minutes"),
        on_site=raw.get("on_site", False),
        travel_minutes=raw.get("travel_minutes", 0),
    )


def _room(raw: dict[str, Any]) -> DefaultRoom:
    return DefaultRoom(
        names=raw["names"], opens=raw["opens"], closes=raw["closes"], capacity=raw.get("capacity")
    )


def _plan(raw: dict[str, Any]) -> DefaultPlan:
    return DefaultPlan(
        names=raw["names"],
        kind=raw["kind"],
        validity_days=raw["validity_days"],
        prices=_prices(raw["prices"]),
        credits=raw.get("credits"),
    )


def _resolve(raw: dict[str, Any], parent: VerticalPack | None) -> VerticalPack:
    """The entry with what it leaves out taken from its parent."""

    def get(name: str, default: Any = None) -> Any:
        if name in raw:
            return raw[name]
        return getattr(parent, name) if parent is not None else default

    fields = (
        tuple(_field(f) for f in raw["client_fields"])
        if "client_fields" in raw
        else (parent.client_fields if parent else ())
    )
    extra = tuple(
        _field(f)
        for f in raw.get("extra_client_fields", ())
        if f["key"] not in {existing.key for existing in fields}
    )
    return VerticalPack(
        key=raw["key"],
        status=raw["status"],
        parent=parent.key if parent else None,
        category=parent.category if parent else raw["key"],
        terms=get("terms", ""),
        client_term=get("client_term", "client"),
        cancellation_window_minutes=get("cancellation_window_minutes", 0),
        booking_requires_plan=get("booking_requires_plan", False),
        default_preset=get("default_preset", "starter"),
        health_form=get("health_form"),
        recommended_modules=tuple(get("recommended_modules", ())),
        default_plans=(
            tuple(_plan(p) for p in raw["default_plans"])
            if "default_plans" in raw
            else (parent.default_plans if parent else ())
        ),
        default_services=(
            tuple(_service(s) for s in raw["default_services"])
            if "default_services" in raw
            else (parent.default_services if parent else ())
        ),
        dependents=get("dependents"),
        dependent_fields=(
            tuple(_field(f) for f in raw["dependent_fields"])
            if "dependent_fields" in raw
            else (parent.dependent_fields if parent else ())
        ),
        dependent_required=get("dependent_required", False),
        time_billing=get("time_billing", False),
        default_rooms=(
            tuple(_room(r) for r in raw["default_rooms"])
            if "default_rooms" in raw
            else (parent.default_rooms if parent else ())
        ),
        client_fields=fields + extra,
    )


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, VerticalPack]:
    """Every catalog entry by key: each category followed by its sub-categories."""
    packs: dict[str, VerticalPack] = {}

    def visit(raw: dict[str, Any], parent: VerticalPack | None) -> None:
        pack = _resolve(raw, parent)
        packs[pack.key] = pack
        for child in raw.get("children", ()):
            visit(child, pack)

    for category in json.loads(path.read_text(encoding="utf-8")):
        visit(category, None)
    return packs


CATALOG: dict[str, VerticalPack] = load_catalog()

# The industries a business can sign up with (live and beta).
VERTICAL_PACKS: dict[str, VerticalPack] = {k: p for k, p in CATALOG.items() if p.is_open}


MAX_NUMBER = 10_000_000


def clean_client_fields(pack: VerticalPack, values: dict[str, object]) -> dict[str, object]:
    """Validates a client's extra fields against the pack; blank values are dropped.
    Raises ValueError with a short reason for unknown fields or invalid values."""
    return clean_fields(pack.client_fields, values)


def clean_fields(fields: tuple[ClientField, ...], values: dict[str, object]) -> dict[str, object]:
    """Validates extra field values against their definitions; blank values are dropped."""
    definitions = {f.key: f for f in fields}
    cleaned: dict[str, object] = {}
    for key, value in values.items():
        definition = definitions.get(key)
        if definition is None:
            raise ValueError(f"unknown field: {key}")
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        text_value = str(value).strip()
        if definition.kind == "number":
            try:
                number = int(text_value)
            except ValueError as error:
                raise ValueError(f"{key}: not a whole number") from error
            if not 0 <= number <= MAX_NUMBER:
                raise ValueError(f"{key}: out of range")
            cleaned[key] = number
        elif definition.kind == "date":
            try:
                cleaned[key] = date.fromisoformat(text_value).isoformat()
            except ValueError as error:
                raise ValueError(f"{key}: not a date") from error
        elif definition.kind == "select":
            if text_value not in definition.options:
                raise ValueError(f"{key}: unknown option")
            cleaned[key] = text_value
        else:
            if len(text_value) > definition.max_length:
                raise ValueError(f"{key}: too long")
            cleaned[key] = text_value
    return cleaned
