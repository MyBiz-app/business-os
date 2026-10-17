"""From gross to net pay for one person and one month (round 6, P5).

Pure arithmetic over a rates table: the gross totals come in (taxable, liable to national
insurance, pension base), the deductions come out as lines, each with the numbers it came from.
Every division rounds half up once, on the line it belongs to, so the lines always add up to the
net pay. The result is a draft for an accountant: it follows the ordinary employee case and
leaves the special cases (tax coordination, a second employer, garnishments) to a person.

The rates are plain data (`app.payroll.rates`); nothing in here knows a year or a law by name."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.payroll.gross import money
from app.payroll.rates import Rates


@dataclass(frozen=True)
class Funds:
    """Pension and study fund percentages of the pension base (employee side, employer side)."""

    pension_employee_pct: Decimal
    pension_employer_pct: Decimal
    severance_pct: Decimal
    study_employee_pct: Decimal = Decimal(0)
    study_employer_pct: Decimal = Decimal(0)


@dataclass
class Line:
    code: str
    amount_minor: int
    base_minor: int | None = None
    percent: str | None = None  # as written, for the payslip

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "amount_minor": self.amount_minor,
            "base_minor": self.base_minor,
            "percent": self.percent,
        }


@dataclass
class Net:
    deductions: list[Line] = field(default_factory=list)  # taken from the employee
    employer: list[Line] = field(default_factory=list)  # paid on top by the employer
    other_deductions_minor: int = 0
    gross_minor: int = 0
    tax_minor: int = 0
    national_insurance_minor: int = 0
    health_minor: int = 0
    pension_minor: int = 0
    study_fund_minor: int = 0
    total_deductions_minor: int = 0
    net_minor: int = 0
    credit_points: str = "0"
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gross_minor": self.gross_minor,
            "tax_minor": self.tax_minor,
            "national_insurance_minor": self.national_insurance_minor,
            "health_minor": self.health_minor,
            "pension_minor": self.pension_minor,
            "study_fund_minor": self.study_fund_minor,
            "other_deductions_minor": self.other_deductions_minor,
            "total_deductions_minor": self.total_deductions_minor,
            "net_minor": self.net_minor,
            "credit_points": self.credit_points,
            "deductions": [line.as_dict() for line in self.deductions],
            "employer": [line.as_dict() for line in self.employer],
            "problems": self.problems,
        }


def _percent(value: Decimal) -> str:
    return format(value.normalize(), "f")


def income_tax(taxable_minor: int, rates: Rates) -> int:
    """Progressive tax on a month's taxable pay, before credit points."""
    tax = Decimal(0)
    floor = 0
    for ceiling, pct in rates.tax_brackets:
        top = taxable_minor if ceiling is None else min(taxable_minor, ceiling)
        if top > floor:
            tax += Decimal(top - floor) * Decimal(str(pct)) / 100
        if ceiling is None or taxable_minor <= ceiling:
            break
        floor = ceiling
    return money(tax)


def _insurance(base: int, reduced_pct: Decimal, full_pct: Decimal, rates: Rates) -> int:
    """Insurance on the reduced rate up to the threshold and the full rate above it, up to the
    maximum base."""
    capped = min(base, rates.insurance_max_minor)
    low = min(capped, rates.insurance_threshold_minor)
    high = max(capped - rates.insurance_threshold_minor, 0)
    return money(Decimal(low) * reduced_pct / 100 + Decimal(high) * full_pct / 100)


def compute_net(
    gross_minor: int,
    taxable_minor: int,
    social_security_minor: int,
    pension_base_minor: int,
    other_deductions_minor: int,
    credit_points: Decimal,
    funds: Funds,
    rates: Rates,
) -> Net:
    result = Net(gross_minor=gross_minor, credit_points=_percent(credit_points))

    credit = money(credit_points * rates.credit_point_minor)
    tax = max(income_tax(taxable_minor, rates) - credit, 0)
    result.tax_minor = tax
    result.deductions.append(Line("income_tax", tax, taxable_minor))

    ni = _insurance(
        social_security_minor,
        rates.ni_employee_reduced_pct,
        rates.ni_employee_full_pct,
        rates,
    )
    health = _insurance(
        social_security_minor,
        rates.health_reduced_pct,
        rates.health_full_pct,
        rates,
    )
    result.national_insurance_minor, result.health_minor = ni, health
    result.deductions.append(Line("national_insurance", ni, social_security_minor))
    result.deductions.append(Line("health_insurance", health, social_security_minor))

    pension = money(Decimal(pension_base_minor) * funds.pension_employee_pct / 100)
    result.pension_minor = pension
    if pension or funds.pension_employee_pct:
        result.deductions.append(
            Line(
                "pension_employee",
                pension,
                pension_base_minor,
                _percent(funds.pension_employee_pct),
            )
        )
    study = money(Decimal(pension_base_minor) * funds.study_employee_pct / 100)
    result.study_fund_minor = study
    if funds.study_employee_pct:
        result.deductions.append(
            Line(
                "study_fund_employee", study, pension_base_minor, _percent(funds.study_employee_pct)
            )
        )
    if other_deductions_minor:
        result.deductions.append(Line("other_deductions", other_deductions_minor))
    result.other_deductions_minor = other_deductions_minor

    result.employer.append(
        Line(
            "pension_employer",
            money(Decimal(pension_base_minor) * funds.pension_employer_pct / 100),
            pension_base_minor,
            _percent(funds.pension_employer_pct),
        )
    )
    result.employer.append(
        Line(
            "severance",
            money(Decimal(pension_base_minor) * funds.severance_pct / 100),
            pension_base_minor,
            _percent(funds.severance_pct),
        )
    )
    if funds.study_employer_pct:
        result.employer.append(
            Line(
                "study_fund_employer",
                money(Decimal(pension_base_minor) * funds.study_employer_pct / 100),
                pension_base_minor,
                _percent(funds.study_employer_pct),
            )
        )
    result.employer.append(
        Line(
            "national_insurance_employer",
            _insurance(
                social_security_minor,
                rates.ni_employer_reduced_pct,
                rates.ni_employer_full_pct,
                rates,
            ),
            social_security_minor,
        )
    )

    result.total_deductions_minor = sum(line.amount_minor for line in result.deductions)
    result.net_minor = gross_minor - result.total_deductions_minor
    if result.net_minor < 0:
        result.problems.append("negative_net")
    return result
