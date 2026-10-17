"""Defaults for pay components and one-off adjustments (round 6, P3).

Each kind carries ordinary-case defaults for the three questions a payslip asks of every line:
is it taxable, is it liable to national insurance, does it count towards the pension base. They
are starting points an accountant can overrule per line, not tax advice."""

from typing import Literal, NamedTuple

ComponentKind = Literal[
    "travel", "meals", "phone", "car", "fixed_addition", "recuperation", "fixed_deduction"
]
AdjustmentKind = Literal["bonus", "holiday_gift", "expense_refund", "deduction"]
Calc = Literal["per_work_day", "monthly", "by_month", "automatic"]


class Flags(NamedTuple):
    taxable: bool
    social_security_liable: bool
    pension_base: bool


COMPONENT_FLAGS: dict[str, Flags] = {
    "travel": Flags(False, False, False),  # up to the daily ceiling
    "meals": Flags(True, True, False),  # the value of vouchers
    "phone": Flags(True, True, False),
    "car": Flags(True, True, False),  # the value of private use
    "fixed_addition": Flags(True, True, True),
    "recuperation": Flags(False, False, False),  # up to the yearly ceiling
    "fixed_deduction": Flags(False, False, False),
}

ADJUSTMENT_FLAGS: dict[str, Flags] = {
    "bonus": Flags(True, True, True),
    "holiday_gift": Flags(False, False, False),  # up to the gift value ceiling
    "expense_refund": Flags(False, False, False),  # against a receipt
    "deduction": Flags(False, False, False),
}

# What the amount of a component means by default for each kind.
DEFAULT_CALC: dict[str, str] = {
    "travel": "per_work_day",
    "meals": "monthly",
    "phone": "monthly",
    "car": "monthly",
    "fixed_addition": "monthly",
    "recuperation": "automatic",
    "fixed_deduction": "monthly",
}


def split_evenly(total_minor: int, count: int) -> list[int]:
    """`total_minor` divided into `count` whole minor units that add up exactly: the first
    `total % count` shares carry the one extra unit."""
    base, extra = divmod(total_minor, count)
    return [base + 1 if index < extra else base for index in range(count)]
