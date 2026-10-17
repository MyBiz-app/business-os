"""Tax credit points (נקודות זיכוי) computed from the answers of a Form 101.

The rules below follow the common Israeli table and are a starting point: the result is shown
as a draft and a payroll manager (or the accountant) can overwrite it with a note. The server
computes; nothing here is decided by the AI. The numbers sit in one place (`RULES`) so a yearly
update is a single edit."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

D = Decimal


_RESIDENT, _WOMAN, _SINGLE_PARENT = D("2.25"), D("0.5"), D("1")
_DISABILITY, _DEGREE, _SOLDIER = D("2"), D("1"), D("2")


@dataclass(frozen=True)
class Rules:
    resident: Decimal = _RESIDENT
    woman: Decimal = _WOMAN
    single_parent: Decimal = _SINGLE_PARENT
    disability_full: Decimal = _DISABILITY
    degree: Decimal = _DEGREE
    # (child age on 31 Dec of the tax year) -> points, by who claims them.
    mother_child_by_age: tuple[tuple[int, int, Decimal], ...] = (
        (0, 0, D("1.5")),
        (1, 5, D("2.5")),
        (6, 17, D("1")),
        (18, 18, D("0.5")),
    )
    other_child_by_age: tuple[tuple[int, int, Decimal], ...] = (
        (0, 0, D("1.5")),
        (1, 5, D("1")),
    )
    # New immigrant, by month since the immigration date: (first month, last month, points).
    immigrant_months: tuple[tuple[int, int, Decimal], ...] = (
        (1, 12, D("3")),
        (13, 30, D("2")),
        (31, 42, D("1")),
    )
    soldier_months: int = 36
    soldier: Decimal = _SOLDIER


RULES = Rules()


def _months_between(start: date, year: int, month: int) -> int:
    """1 for the month containing `start`, 2 for the next, and so on."""
    return (year - start.year) * 12 + (month - start.month) + 1


def _monthly(start: date | None, tax_year: int, bands: tuple[tuple[int, int, Decimal], ...]):
    if start is None:
        return D(0)
    total = D(0)
    for month in range(1, 13):
        index = _months_between(start, tax_year, month)
        for first, last, points in bands:
            if first <= index <= last:
                total += points
    return total / 12


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def compute(answers: dict[str, Any], tax_year: int, rules: Rules = RULES) -> Decimal:
    """The credit points for the tax year, two decimals, never below zero."""
    points = D(0)
    if answers.get("resident", True):
        points += rules.resident
    female = answers.get("gender") == "female"
    if female:
        points += rules.woman
    for child in answers.get("children", []):
        age = tax_year - int(child["birth_year"])
        if age < 0:
            continue
        if not child.get("lives_with_me", True):
            continue
        table = rules.mother_child_by_age if female else rules.other_child_by_age
        for first, last, value in table:
            if first <= age <= last:
                points += value
    if answers.get("single_parent"):
        points += rules.single_parent
    points += _monthly(_date(answers.get("new_immigrant_date")), tax_year, rules.immigrant_months)
    soldier = _date(answers.get("discharged_soldier_date"))
    if soldier is not None:
        band = ((1, rules.soldier_months, rules.soldier),)
        points += _monthly(soldier, tax_year, band)
    degree_year = answers.get("academic_degree_year")
    if degree_year is not None and 0 <= tax_year - int(degree_year) <= 1:
        points += rules.degree
    if int(answers.get("disability_percent") or 0) >= 100:
        points += rules.disability_full
    return max(points, D(0)).quantize(D("0.01"))
