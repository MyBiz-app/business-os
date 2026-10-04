"""Vertical packs: configuration that adapts the vertical-agnostic core to an industry.

The core never branches on the vertical; it reads the pack. Packs grow with each sprint
(terminology, default services, roles, metrics)."""

from dataclasses import dataclass, field


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
    """A service every new business of the vertical starts with (editable afterwards)."""

    names: dict[str, str]  # by locale
    duration_minutes: int
    booking_mode: str  # "class" | "appointment"
    prices: dict[str, int]  # minor units, by currency
    color: str
    capacity: int = 1


@dataclass(frozen=True)
class VerticalPack:
    key: str
    client_term: str  # i18n key suffix for what the business calls its clients
    cancellation_window_minutes: int  # default booking policy for new businesses
    booking_requires_plan: bool  # clients need a valid plan to book in the client app
    default_preset: str  # modules a new business starts with (app/modules.py PRESETS)
    requires_health_declaration: bool = False  # clients sign app/health.py's form to book
    default_plans: tuple[DefaultPlan, ...] = field(default_factory=tuple)
    default_services: tuple[DefaultService, ...] = field(default_factory=tuple)


FITNESS = VerticalPack(
    key="fitness",
    client_term="member",
    cancellation_window_minutes=120,
    booking_requires_plan=True,
    default_preset="growing",
    requires_health_declaration=True,
    default_plans=(
        DefaultPlan(
            names={"he": "מנוי חודשי ללא הגבלה", "en": "Monthly unlimited"},
            kind="membership",
            validity_days=30,
            prices={"ILS": 45000, "USD": 12900, "EUR": 11900},
        ),
        DefaultPlan(
            names={"he": "כרטיסייה 10 כניסות", "en": "10-class card"},
            kind="punch_card",
            validity_days=120,
            credits=10,
            prices={"ILS": 60000, "USD": 18000, "EUR": 16000},
        ),
        DefaultPlan(
            names={"he": "כניסה בודדת", "en": "Single class"},
            kind="punch_card",
            validity_days=30,
            credits=1,
            prices={"ILS": 7000, "USD": 2000, "EUR": 1800},
        ),
    ),
)


def _service(he: str, en: str, minutes: int, ils: int, color: str) -> DefaultService:
    """An appointment service, priced in ILS with rough USD/EUR equivalents."""
    usd = round(ils * 0.27 / 100) * 100
    return DefaultService(
        names={"he": he, "en": en},
        duration_minutes=minutes,
        booking_mode="appointment",
        prices={"ILS": ils, "USD": usd, "EUR": round(usd * 0.92 / 100) * 100},
        color=color,
    )


BEAUTY = VerticalPack(
    key="beauty",
    client_term="client",
    cancellation_window_minutes=180,
    booking_requires_plan=False,
    default_preset="growing",
    default_services=(
        _service("תספורת גברים", "Men's haircut", 30, 8000, "#6366f1"),
        _service("תספורת ועיצוב נשים", "Women's cut & style", 60, 18000, "#ec4899"),
        _service("צבע שורשים", "Root color", 90, 25000, "#f59e0b"),
        _service("עיצוב זקן", "Beard trim", 20, 5000, "#10b981"),
    ),
)

CLINIC = VerticalPack(
    key="clinic",
    client_term="patient",
    cancellation_window_minutes=1440,
    booking_requires_plan=False,
    default_preset="growing",
    default_services=(
        _service("פגישת היכרות", "First visit", 60, 35000, "#14b8a6"),
        _service("טיפול", "Treatment", 45, 30000, "#6366f1"),
        _service("פגישת מעקב", "Follow-up", 30, 20000, "#8b5cf6"),
    ),
)

GARAGE = VerticalPack(
    key="garage",
    client_term="customer",
    cancellation_window_minutes=1440,
    booking_requires_plan=False,
    default_preset="starter",
    default_services=(
        _service("טיפול תקופתי", "Periodic service", 120, 60000, "#f59e0b"),
        _service("החלפת שמן ומסננים", "Oil & filter change", 45, 25000, "#0ea5e9"),
        _service("בדיקה לפני טסט", "Pre-inspection check", 60, 20000, "#10b981"),
        _service("אבחון תקלה", "Diagnostics", 60, 30000, "#ef4444"),
    ),
)

VERTICAL_PACKS: dict[str, VerticalPack] = {
    pack.key: pack for pack in (FITNESS, BEAUTY, CLINIC, GARAGE)
}
