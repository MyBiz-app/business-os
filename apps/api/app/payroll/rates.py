"""The law-driven rates the net pay needs, for one month (round 6, P5).

`resolve` takes the rows of `payroll_rates` valid on the first day of the month. Rows
the table does not have yet (income tax brackets, national insurance, health insurance) fall
back to the example values below, so a business never has a payslip without rates. The examples
are the published figures of 2025 as the spec lists them and are NOT verified: every payslip
stays a draft for the accountant, and the accountant's check is what makes the figures count.
A row in the table always wins, so updating a year is a data change, not a code change."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

EXAMPLE_SOURCE = "example 2025 figures, to be verified by an accountant"

# Monthly brackets, in minor units: (upper bound or None, percent).
EXAMPLE_TAX_BRACKETS: list[tuple[int | None, int]] = [
    (701000, 10),
    (1006000, 14),
    (1615000, 20),
    (2244000, 31),
    (4669000, 35),
    (6013000, 47),
    (None, 50),
]


@dataclass(frozen=True)
class Rates:
    tax_brackets: list[tuple[int | None, int]]
    credit_point_minor: int
    insurance_threshold_minor: int
    insurance_max_minor: int
    ni_employee_reduced_pct: Decimal
    ni_employee_full_pct: Decimal
    health_reduced_pct: Decimal
    health_full_pct: Decimal
    ni_employer_reduced_pct: Decimal
    ni_employer_full_pct: Decimal
    pension_employee_pct: Decimal
    pension_employer_pct: Decimal
    severance_pct: Decimal
    example_keys: tuple[str, ...]  # the rates that came from the examples above


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def resolve(table: dict[str, dict[str, Any]]) -> Rates:
    """`table` maps a rate key to its value for the month (rows of `payroll_rates`)."""
    examples: list[str] = []

    def pick(key: str, fallback: Any) -> Any:
        if key in table:
            return table[key]
        examples.append(key)
        return fallback

    tax = pick("income_tax_brackets", {"brackets": EXAMPLE_TAX_BRACKETS})
    brackets = [(b[0], int(b[1])) for b in tax["brackets"]]
    insurance = pick(
        "national_insurance",
        {
            "threshold_minor": 752200,
            "max_minor": 5191000,
            "employee_reduced_pct": 1.04,
            "employee_full_pct": 7,
            "health_reduced_pct": 3.23,
            "health_full_pct": 5.17,
            "employer_reduced_pct": 3.55,
            "employer_full_pct": 7.6,
        },
    )
    pension = table.get("pension_defaults") or {
        "employee_pct": 6,
        "employer_pct": 6.5,
        "severance_pct": 6,
    }
    return Rates(
        tax_brackets=brackets,
        credit_point_minor=int((table.get("credit_point_monthly") or {"minor": 24200})["minor"]),
        insurance_threshold_minor=int(insurance["threshold_minor"]),
        insurance_max_minor=int(insurance["max_minor"]),
        ni_employee_reduced_pct=_decimal(insurance["employee_reduced_pct"]),
        ni_employee_full_pct=_decimal(insurance["employee_full_pct"]),
        health_reduced_pct=_decimal(insurance["health_reduced_pct"]),
        health_full_pct=_decimal(insurance["health_full_pct"]),
        ni_employer_reduced_pct=_decimal(insurance["employer_reduced_pct"]),
        ni_employer_full_pct=_decimal(insurance["employer_full_pct"]),
        pension_employee_pct=_decimal(pension["employee_pct"]),
        pension_employer_pct=_decimal(pension["employer_pct"]),
        severance_pct=_decimal(pension["severance_pct"]),
        example_keys=tuple(examples),
    )
