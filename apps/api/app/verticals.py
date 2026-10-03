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
class VerticalPack:
    key: str
    client_term: str  # i18n key suffix for what the business calls its clients
    cancellation_window_minutes: int  # default booking policy for new businesses
    booking_requires_plan: bool  # clients need a valid plan to book in the client app
    default_preset: str  # modules a new business starts with (app/modules.py PRESETS)
    requires_health_declaration: bool = False  # clients sign app/health.py's form to book
    default_plans: tuple[DefaultPlan, ...] = field(default_factory=tuple)


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

VERTICAL_PACKS: dict[str, VerticalPack] = {FITNESS.key: FITNESS}
