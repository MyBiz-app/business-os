"""Corrective payslips and the annual summary (round 6, P6).

An approved month is locked, so a mistake found afterwards is fixed with a corrective payslip: a
new version for one person and month that keeps the reason and the adjustment lines, works the net
pay out again from the dated rates table and states the difference to pay (or recover). The
approved run is never edited. Corrections are always marked "draft for the accountant": the
accountant has to check the corrected figures. Adjustments are treated as ordinary taxable pay,
liable to insurance and pension; anything special goes to the accountant.

The annual summary adds up the approved months of a tax year per person (the latest corrective
payslip of a month replaces its original). It is the data behind Form 106, which the accountant
files; nothing is filed or sent from here."""

import datetime as dt
import json
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, require
from app.api.pay_components import _audit, _below
from app.api.payroll_runs import (
    XLSX,
    PeriodPath,
    _conflict,
    _csv,
    _ensure_unscoped,
    _first,
    _rates,
    _run_row,
    _unprocessable,
    _xlsx,
)
from app.api.payslips import (
    _credit_points,
    _funds,
    _line_rows,
    _profiles,
    correction_row,
    payslip_pdf,
)
from app.core.permissions import Permission
from app.files import keep_copy, safe_name
from app.payroll.gate import require_open
from app.payroll.net import compute_net
from app.payroll.rates import resolve

router = APIRouter(tags=["payroll"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_READ))]
ApproveDep = Annotated[TenantContext, Depends(require_open(Permission.PAYROLL_APPROVE))]
YearPath = Annotated[int, Path(ge=2000, le=2100)]
LIMIT_MINOR = 100_000_000


class CorrectionItem(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    amount_minor: int = Field(
        ge=-LIMIT_MINOR, le=LIMIT_MINOR, description="Added to the pay; negative takes away"
    )


class CorrectionBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    items: list[CorrectionItem] = Field(min_length=1, max_length=10)


class Correction(BaseModel):
    version: int = Field(description="1 is the first correction; the original payslip is 0")
    reason: str
    items: list[CorrectionItem]
    previous_net_minor: int
    net_minor: int
    difference_minor: int = Field(description="Net now less net before: to pay, or to recover")
    created_at: dt.datetime


def _present(row: Any) -> Correction:
    return Correction(
        version=row["version"],
        reason=row["reason"],
        items=[CorrectionItem(**item) for item in row["items"]],
        previous_net_minor=row["previous_net_minor"],
        net_minor=row["net"]["net_minor"],
        difference_minor=row["difference_minor"],
        created_at=row["created_at"],
    )


def _member_line(context: TenantContext, run: Any, user_id: UUID) -> Any:
    """The person's line in an approved run, when the reader may see their pay."""
    line = next(
        (r for r in _line_rows(context.session, run["id"]) if r["user_id"] == user_id), None
    )
    if line is None or not _below(context, line["role"]):
        raise not_found()
    return line


@router.get("/payroll/runs/{period}/payslips/{user_id}/corrections")
def list_corrections(period: PeriodPath, user_id: UUID, context: ReadDep) -> list[Correction]:
    _ensure_unscoped(context)
    run = _run_row(context.session, _first(period))
    _member_line(context, run, user_id)
    rows = context.session.execute(
        text("""
            SELECT * FROM app.payslip_corrections
            WHERE run_id = :run AND user_id = :user ORDER BY version
        """),
        {"run": run["id"], "user": user_id},
    ).mappings()
    return [_present(row) for row in rows]


@router.post("/payroll/runs/{period}/payslips/{user_id}/corrections", status_code=201)
def issue_correction(
    period: PeriodPath, user_id: UUID, body: CorrectionBody, context: ApproveDep, user: UserDep
) -> Correction:
    """A new corrective payslip. Only an approved month can be corrected, and only by the owner."""
    _ensure_unscoped(context)
    session = context.session
    first = _first(period)
    run = _run_row(session, first)
    if run["stage"] != "approved":
        raise _conflict("run_not_approved")
    line = _member_line(context, run, user_id)
    original = (line["inputs"] or {}).get("net")
    if original is None:
        raise _conflict("run_not_approved")
    previous = correction_row(session, run["id"], user_id)
    previous_net = previous["net"] if previous else original
    version = previous["version"] + 1 if previous else 1
    earlier = session.execute(
        text("""
                SELECT coalesce(sum(adjustment_minor), 0) FROM app.payslip_corrections
                WHERE run_id = :run AND user_id = :user
            """),
        {"run": run["id"], "user": user_id},
    ).scalar_one()
    adjustment = sum(item.amount_minor for item in body.items)
    total = int(earlier) + adjustment
    if adjustment == 0:
        raise _unprocessable("nothing_to_correct")
    rates = resolve(_rates(session, first))
    profile = _profiles(session, context.tenant_id).get(user_id)
    net = compute_net(
        line["gross_minor"] + total,
        line["taxable_minor"] + total,
        line["social_security_minor"] + total,
        line["pension_base_minor"] + total,
        line["deductions_minor"],
        _credit_points(session, user_id, first.year),
        _funds(profile, rates),
        rates,
    ).as_dict()
    if net["net_minor"] < 0:
        raise _unprocessable("negative_net")
    row = (
        session.execute(
            text("""
                INSERT INTO app.payslip_corrections
                    (tenant_id, run_id, user_id, version, supersedes_id, reason, items,
                     adjustment_minor, previous_net_minor, difference_minor, net, created_by)
                VALUES (:tenant, :run, :user, :version, :supersedes, :reason,
                        CAST(:items AS jsonb), :adjustment, :previous_net, :difference,
                        CAST(:net AS jsonb), :actor)
                RETURNING *
            """),
            {
                "tenant": context.tenant_id,
                "run": run["id"],
                "user": user_id,
                "version": version,
                "supersedes": previous["id"] if previous else None,
                "reason": body.reason,
                "items": json.dumps([item.model_dump() for item in body.items]),
                "adjustment": adjustment,
                "previous_net": previous_net["net_minor"],
                "difference": net["net_minor"] - previous_net["net_minor"],
                "net": json.dumps(net),
                "actor": user.id,
            },
        )
        .mappings()
        .one()
    )
    _audit(
        session,
        context.tenant_id,
        "payroll.payslip_corrected",
        "payroll_run",
        run["id"],
        member=str(user_id),
        version=version,
        difference_minor=row["difference_minor"],
    )
    # A copy goes to the employee's Files area like the regular payslips; a full or unreachable
    # storage skips the copy and never fails the correction.
    keep_copy(
        session,
        context.tenant_id,
        "payroll",
        name=f"payslip-{first:%Y-%m}-{safe_name(line['full_name'])}-v{version}.pdf",
        content=payslip_pdf(session, context.tenant_id, run, user_id, row),
        owner_user_id=user_id,
    )
    return _present(row)


# -- the annual summary ---------------------------------------------------------------------------


class AnnualPerson(BaseModel):
    user_id: UUID
    full_name: str | None
    months: int
    corrected_months: int
    gross_minor: int
    income_tax_minor: int
    national_insurance_minor: int
    health_minor: int
    pension_employee_minor: int
    study_fund_employee_minor: int
    other_deductions_minor: int
    net_minor: int
    employer_minor: int = Field(description="Pension, severance, study fund and insurance")


class AnnualSummary(BaseModel):
    year: int
    currency: str
    draft: bool = Field(description="Some month was not yet checked by an accountant")
    people: list[AnnualPerson]


def _annual(context: TenantContext, year: int) -> AnnualSummary:
    rows = context.session.execute(
        text("""
            SELECT l.user_id, coalesce(u.full_name, u.email) AS full_name, m.role, r.currency,
                   r.accountant_checked_at,
                   coalesce(c.net, l.inputs -> 'net') AS net, c.version IS NOT NULL AS corrected
            FROM app.payroll_run_lines l
            JOIN app.payroll_runs r ON r.id = l.run_id
            JOIN app.users u ON u.id = l.user_id
            JOIN app.tenant_members m ON m.tenant_id = l.tenant_id AND m.user_id = l.user_id
            LEFT JOIN LATERAL (
                SELECT net, version FROM app.payslip_corrections k
                WHERE k.run_id = l.run_id AND k.user_id = l.user_id
                ORDER BY k.version DESC LIMIT 1
            ) c ON true
            WHERE r.stage = 'approved' AND r.period >= make_date(:year, 1, 1)
              AND r.period < make_date(:year + 1, 1, 1) AND l.inputs -> 'net' IS NOT NULL
            ORDER BY coalesce(u.full_name, u.email), l.user_id, r.period
        """),
        {"year": year},
    ).mappings()
    people: dict[UUID, AnnualPerson] = {}
    currency, draft = "ILS", False
    for row in rows:
        if not _below(context, row["role"]):
            continue
        currency = row["currency"]
        draft = draft or row["accountant_checked_at"] is None or row["corrected"]
        net = row["net"]
        person = people.setdefault(
            row["user_id"],
            AnnualPerson(
                user_id=row["user_id"],
                full_name=row["full_name"],
                months=0,
                corrected_months=0,
                gross_minor=0,
                income_tax_minor=0,
                national_insurance_minor=0,
                health_minor=0,
                pension_employee_minor=0,
                study_fund_employee_minor=0,
                other_deductions_minor=0,
                net_minor=0,
                employer_minor=0,
            ),
        )
        person.months += 1
        person.corrected_months += 1 if row["corrected"] else 0
        person.gross_minor += net["gross_minor"]
        person.income_tax_minor += net["tax_minor"]
        person.national_insurance_minor += net["national_insurance_minor"]
        person.health_minor += net["health_minor"]
        person.pension_employee_minor += net["pension_minor"]
        person.study_fund_employee_minor += net["study_fund_minor"]
        person.other_deductions_minor += net["other_deductions_minor"]
        person.net_minor += net["net_minor"]
        person.employer_minor += sum(line["amount_minor"] for line in net["employer"])
    return AnnualSummary(year=year, currency=currency, draft=draft, people=list(people.values()))


@router.get("/payroll/annual/{year}")
def annual_summary(year: YearPath, context: ReadDep) -> AnnualSummary:
    """Per person totals of the tax year's approved months, the basis for Form 106."""
    _ensure_unscoped(context)
    return _annual(context, year)


@router.get("/payroll/annual/{year}/export")
def annual_export(
    year: YearPath,
    context: ReadDep,
    file_format: Annotated[Literal["csv", "xlsx"], Query(alias="format")] = "xlsx",
) -> Response:
    _ensure_unscoped(context)
    summary = _annual(context, year)
    major = Decimal(100)
    header = [
        "employee",
        "months",
        "corrected_months",
        "gross",
        "income_tax",
        "national_insurance",
        "health",
        "pension_employee",
        "study_fund_employee",
        "other_deductions",
        "net",
        "employer_contributions",
        "currency",
    ]
    rows = [
        [
            person.full_name,
            person.months,
            person.corrected_months,
            *[
                Decimal(value) / major
                for value in (
                    person.gross_minor,
                    person.income_tax_minor,
                    person.national_insurance_minor,
                    person.health_minor,
                    person.pension_employee_minor,
                    person.study_fund_employee_minor,
                    person.other_deductions_minor,
                    person.net_minor,
                    person.employer_minor,
                )
            ],
            summary.currency,
        ]
        for person in summary.people
    ]
    _audit(
        context.session,
        context.tenant_id,
        "payroll.annual_exported",
        "tenant",
        context.tenant_id,
        year=year,
        format=file_format,
    )
    if file_format == "csv":
        body, kind = _csv(header, rows), "text/csv; charset=utf-8"
    else:
        body, kind = _xlsx(header, rows), XLSX
    return Response(
        content=body,
        media_type=kind,
        headers={"Content-Disposition": f'attachment; filename="payroll-{year}.{file_format}"'},
    )
