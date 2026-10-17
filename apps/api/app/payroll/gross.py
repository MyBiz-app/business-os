"""Gross pay of one person for one month (round 6, P4).

Pure arithmetic: the terms of employment, the hours (from the time clock), the fixed components
and the one-off amounts come in; the pay lines come out, each with the numbers it came from, so
the screen can answer "why this amount?". Money is integer minor units; every division rounds
half up once, on the line it belongs to, so the lines always add up to the total.

What counts as gross: the base, overtime, every addition (fixed or one-off). Deductions are kept
apart (they come off the net pay, P5). The flags on each line (taxable, liable to national
insurance, in the pension base) feed the later steps; the totals per flag are kept too."""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.payroll.components import Flags
from app.schedule.time_clock import Breakdown, ClockRules

WEEKS_PER_YEAR = Decimal(52)
MONTHS_PER_YEAR = Decimal(12)
# Base and overtime of an employee: taxable, liable to national insurance; the pension base is the
# base pay only (overtime joins it by agreement, which an accountant sets per person).
BASE_FLAGS = Flags(True, True, True)
OVERTIME_FLAGS = Flags(True, True, False)
NO_FLAGS = Flags(False, False, False)


@dataclass(frozen=True)
class Terms:
    employment_type: str  # global | hourly | global_overtime
    monthly_amount_minor: int | None
    hourly_rate_minor: int | None
    scope_pct: Decimal = Decimal(100)


@dataclass(frozen=True)
class Component:
    id: str
    kind: str
    name: str
    calc: str  # per_work_day | monthly | by_month | automatic
    amount_minor: int | None
    cap_minor: int | None
    flags: Flags
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True)
class Adjustment:
    id: str
    kind: str  # bonus | holiday_gift | expense_refund | deduction
    amount_minor: int
    note: str | None
    flags: Flags


@dataclass
class Item:
    """One line of the pay: `section` is base, overtime, component, adjustment or deduction."""

    section: str
    code: str
    label: str
    amount_minor: int
    quantity: str | None = None  # hours or days, as written
    unit_minor: int | None = None
    percent: int | None = None
    source: str | None = None  # id of the component or adjustment
    flags: Flags = NO_FLAGS

    def as_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "code": self.code,
            "label": self.label,
            "amount_minor": self.amount_minor,
            "quantity": self.quantity,
            "unit_minor": self.unit_minor,
            "percent": self.percent,
            "source": self.source,
            "taxable": self.flags.taxable,
            "social_security_liable": self.flags.social_security_liable,
            "pension_base": self.flags.pension_base,
        }


@dataclass
class Gross:
    items: list[Item] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # codes the caller turns into warnings
    base_minor: int = 0
    overtime_minor: int = 0
    components_minor: int = 0
    adjustments_minor: int = 0
    deductions_minor: int = 0
    gross_minor: int = 0
    taxable_minor: int = 0
    social_security_minor: int = 0
    pension_base_minor: int = 0


def money(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _hours(value: float) -> Decimal:
    return Decimal(str(value))


def _text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def hourly_rate(terms: Terms, rules: ClockRules) -> tuple[int | None, bool]:
    """The hourly rate in minor units, and whether it was derived from the monthly amount (a
    month is `week_hours` x 52 / 12 hours of full scope)."""
    if terms.hourly_rate_minor is not None:
        return terms.hourly_rate_minor, False
    if terms.monthly_amount_minor is None:
        return None, False
    month_hours = Decimal(str(rules.week_hours)) * WEEKS_PER_YEAR / MONTHS_PER_YEAR
    return money(Decimal(terms.monthly_amount_minor) / month_hours), True


def active_in(component: Component, first: date, last: date) -> bool:
    return component.valid_from <= last and (
        component.valid_to is None or component.valid_to >= first
    )


def compute_gross(
    terms: Terms,
    hours: Breakdown,
    work_days: int,
    components: list[Component],
    adjustments: list[Adjustment],
    rules: ClockRules,
    first: date,
    last: date,
    typed: dict[str, int],
) -> Gross:
    """`typed` holds the amounts the payroll manager typed in for this month, by component id
    (for components counted "by month" and those without an automatic rate yet)."""
    result = Gross()

    def add(item: Item) -> None:
        result.items.append(item)

    kind = terms.employment_type
    if kind in ("global", "global_overtime"):
        if terms.monthly_amount_minor is None:
            result.problems.append("missing_terms")
        else:
            amount = money(Decimal(terms.monthly_amount_minor) * terms.scope_pct / 100)
            add(
                Item(
                    "base",
                    "monthly",
                    "monthly",
                    amount,
                    unit_minor=terms.monthly_amount_minor,
                    percent=int(terms.scope_pct)
                    if terms.scope_pct == int(terms.scope_pct)
                    else None,
                    flags=BASE_FLAGS,
                )
            )
    if kind == "hourly":
        if terms.hourly_rate_minor is None:
            result.problems.append("missing_terms")
        else:
            rate = terms.hourly_rate_minor
            worked = _hours(hours.regular)
            add(
                Item(
                    "base",
                    "hourly",
                    "hourly",
                    money(Decimal(rate) * worked),
                    quantity=_text(worked),
                    unit_minor=rate,
                    flags=BASE_FLAGS,
                )
            )
    if kind in ("hourly", "global_overtime"):
        rate, derived = hourly_rate(terms, rules)
        if rate is None:
            if "missing_terms" not in result.problems:
                result.problems.append("missing_terms")
        else:
            if derived:
                result.problems.append("derived_hourly_rate")
            for code, worked, percent in (
                ("overtime_tier1", hours.tier1, rules.tier1_percent),
                ("overtime_tier2", hours.tier2, rules.tier2_percent),
                ("rest_day", hours.rest_day, rules.rest_day_percent),
            ):
                if worked:
                    count = _hours(worked)
                    add(
                        Item(
                            "overtime",
                            code,
                            code,
                            money(Decimal(rate) * count * percent / 100),
                            quantity=_text(count),
                            unit_minor=rate,
                            percent=percent,
                            flags=OVERTIME_FLAGS,
                        )
                    )

    for component in components:
        if not active_in(component, first, last):
            continue
        amount: int
        quantity: str | None = None
        if component.id in typed:
            amount = typed[component.id]
        elif component.calc == "per_work_day":
            amount = (component.amount_minor or 0) * work_days
            quantity = str(work_days)
        elif component.calc == "monthly":
            amount = component.amount_minor or 0
        else:
            amount = 0
            result.problems.append(
                f"typed_amount_missing:{component.id}"
                if component.calc == "by_month"
                else f"automatic_rate_missing:{component.id}"
            )
        if component.cap_minor is not None:
            amount = min(amount, component.cap_minor)
        add(
            Item(
                "deduction" if component.kind == "fixed_deduction" else "component",
                component.kind,
                component.name,
                amount,
                quantity=quantity,
                unit_minor=component.amount_minor if component.calc == "per_work_day" else None,
                source=component.id,
                flags=component.flags,
            )
        )
    for adjustment in adjustments:
        add(
            Item(
                "deduction" if adjustment.kind == "deduction" else "adjustment",
                adjustment.kind,
                adjustment.note or adjustment.kind,
                adjustment.amount_minor,
                source=adjustment.id,
                flags=adjustment.flags,
            )
        )

    for item in result.items:
        match item.section:
            case "base":
                result.base_minor += item.amount_minor
            case "overtime":
                result.overtime_minor += item.amount_minor
            case "component":
                result.components_minor += item.amount_minor
            case "adjustment":
                result.adjustments_minor += item.amount_minor
            case "deduction":
                result.deductions_minor += item.amount_minor
        if item.section == "deduction":
            continue
        result.gross_minor += item.amount_minor
        if item.flags.taxable:
            result.taxable_minor += item.amount_minor
        if item.flags.social_security_liable:
            result.social_security_minor += item.amount_minor
        if item.flags.pension_base:
            result.pension_base_minor += item.amount_minor
    return result
