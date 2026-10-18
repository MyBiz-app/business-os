"""The monthly payroll run up to gross pay (round 6, P4).

A run is built for a month from the employment terms (P1), the approved time clock hours (P2),
the fixed pay components and the one-off amounts (P3). It moves through four stages:

1. `hours`: the clocked hours of the month are checked; moving on locks them.
2. `additions`: bonuses and one-off amounts, amounts typed in for this month.
3. `review`: every warning is fixed or acknowledged.
4. `approved`: only the owner (`payroll.approve`); the month is then locked.

Each person's line is a snapshot with the numbers it came from ("why this amount?"). Net pay, the
payslip PDF and the bank file are P5. `payroll.read` sees the run (people at one's own level or
above stay hidden, owners see all), `payroll.manage` builds and moves it, and a person kept to
some branches never reaches it: a month's pay is a business-wide number."""

import calendar
import csv
import datetime as dt
import io
import json
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, UserDep, require
from app.api.pay_components import _audit, _below
from app.api.time_clock import _clock_rules, _month_bounds, _time_zone, _worked, load_rules
from app.core.permissions import Permission
from app.files import store_file, system_folder_id
from app.payroll.components import Flags
from app.payroll.gate import require_open
from app.payroll.gross import Adjustment, Component, Gross, Terms, compute_gross
from app.schedule.time_clock import Breakdown

router = APIRouter(tags=["payroll"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_READ))]
ManageDep = Annotated[TenantContext, Depends(require_open(Permission.PAYROLL_MANAGE))]
ApproveDep = Annotated[TenantContext, Depends(require_open(Permission.PAYROLL_APPROVE))]
PeriodPath = Annotated[str, Path(pattern=r"^\d{4}-\d{2}$")]

STAGES = ("hours", "additions", "review", "approved")
# Must be fixed before the run can move on; they cannot be acknowledged.
ERRORS = {
    "missing_terms",
    "hours_not_approved",
    "open_clock",
    "pending_adjustments",
    "typed_amount_missing",
}
# Moving to the next stage needs none of these.
BLOCKS = {
    "hours": {"hours_not_approved", "open_clock"},
    "additions": {"missing_terms", "pending_adjustments", "typed_amount_missing"},
    "review": ERRORS,
}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


class Hours(BaseModel):
    total: float = 0
    regular: float = 0
    tier1: float = 0
    tier2: float = 0
    rest_day: float = 0


class RunItem(BaseModel):
    section: Literal["base", "overtime", "component", "adjustment", "deduction"]
    code: str
    label: str
    amount_minor: int
    quantity: str | None = None
    unit_minor: int | None = None
    percent: int | None = None
    source: UUID | None = None
    taxable: bool
    social_security_liable: bool
    pension_base: bool


class RunWarning(BaseModel):
    key: str = Field(description="`code`, or `code:ref` when it concerns one component")
    code: str
    ref: UUID | None = None
    severity: Literal["error", "warning"]
    acknowledged: bool = False


class RunLine(BaseModel):
    user_id: UUID
    full_name: str | None
    employment_type: str
    hours: Hours
    work_days: int
    base_minor: int
    overtime_minor: int
    components_minor: int
    adjustments_minor: int
    deductions_minor: int
    gross_minor: int
    taxable_minor: int
    social_security_minor: int
    pension_base_minor: int
    items: list[RunItem]
    warnings: list[RunWarning]
    typed: dict[UUID, int] = Field(description="Amounts typed in for this month, by component")
    ready: bool = Field(description="No error and every warning acknowledged")


class RunSummary(BaseModel):
    people: int
    gross_minor: int
    deductions_minor: int
    previous_gross_minor: int | None
    open_errors: int
    open_warnings: int


class RunNote(BaseModel):
    code: str
    names: list[str]


class Run(BaseModel):
    period: dt.date
    stage: Literal["hours", "additions", "review", "approved"]
    currency: str
    payslips_draft: bool = Field(
        description="Payslips stay drafts until an accountant has checked the run"
    )
    approved_at: dt.datetime | None
    accountant_checked_at: dt.datetime | None
    summary: RunSummary
    notes: list[RunNote]
    lines: list[RunLine]


class RunRow(BaseModel):
    period: dt.date
    stage: Literal["hours", "additions", "review", "approved"]
    gross_minor: int
    people: int


class RunCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")


class StageBody(BaseModel):
    stage: Literal["hours", "additions", "review", "approved"]


class TypedAmount(BaseModel):
    component_id: UUID
    amount_minor: int | None = Field(
        ge=0, description="The amount for this month; null takes the typed amount away"
    )


class Acknowledge(BaseModel):
    key: str = Field(max_length=80)
    acknowledged: bool = True


# -- working out the lines -----------------------------------------------------------------------


def _first(period: str) -> dt.date:
    return dt.datetime.strptime(period, "%Y-%m").date()


def _last(first: dt.date) -> dt.date:
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])


def _calendar_days(first: dt.date, per_week: int) -> int:
    """Work days of a month for someone on a fixed week: Sunday first, `per_week` days."""
    days = [6, 0, 1, 2, 3, 4, 5][: max(1, min(per_week, 7))]
    return sum(
        1
        for day in range(1, calendar.monthrange(first.year, first.month)[1] + 1)
        if first.replace(day=day).weekday() in days
    )


def _ensure_unscoped(context: TenantContext) -> None:
    if context.branches is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def _rates(session: Session, first: dt.date) -> dict[str, dict[str, Any]]:
    rows = session.execute(
        text("""
            SELECT DISTINCT ON (rate_key) rate_key, value FROM app.payroll_rates
            WHERE valid_from <= :day ORDER BY rate_key, valid_from DESC
        """),
        {"day": first},
    ).all()
    return {key: value for key, value in rows}


def _flags(row: Any) -> Flags:
    return Flags(row["taxable"], row["social_security_liable"], row["pension_base"])


class Built:
    def __init__(self, user_id: UUID, role: str, name: str | None, gross: Gross) -> None:
        self.user_id, self.role, self.name, self.gross = user_id, role, name, gross
        self.hours = Breakdown()
        self.work_days = 0
        self.employment_type = "global"
        self.problems: list[str] = []


def _build(session: Session, tenant_id: UUID, first: dt.date) -> tuple[list[Built], list[RunNote]]:
    time_zone = _time_zone(session)
    rules = _clock_rules(load_rules(session))
    start, end = _month_bounds(first, time_zone)
    last = _last(first)
    rates = _rates(session, first)
    min_hourly = (rates.get("min_wage_hourly") or {}).get("minor")
    min_monthly = (rates.get("min_wage_monthly") or {}).get("minor")

    people = (
        session.execute(
            text("""
            SELECT p.user_id, p.employment_type, p.monthly_amount_minor, p.hourly_rate_minor,
                   p.scope_pct, p.work_days_per_week, p.start_date, p.bank_last4,
                   m.role, u.full_name, u.email
            FROM app.employment_profiles p
            JOIN app.tenant_members m ON m.tenant_id = p.tenant_id AND m.user_id = p.user_id
            JOIN app.users u ON u.id = p.user_id
            WHERE p.tenant_id = :tenant AND (p.start_date IS NULL OR p.start_date <= :last)
            ORDER BY coalesce(u.full_name, u.email), p.user_id
        """),
            {"tenant": tenant_id, "last": last},
        )
        .mappings()
        .all()
    )
    components: dict[UUID, list[Component]] = {}
    for row in session.execute(
        text("""
            SELECT id, user_id, kind, name, calc, amount_minor, cap_minor, taxable,
                   social_security_liable, pension_base, valid_from, valid_to
            FROM app.pay_components WHERE tenant_id = :tenant ORDER BY valid_from, created_at
        """),
        {"tenant": tenant_id},
    ).mappings():
        components.setdefault(row["user_id"], []).append(
            Component(
                id=str(row["id"]),
                kind=row["kind"],
                name=row["name"],
                calc=row["calc"],
                amount_minor=row["amount_minor"],
                cap_minor=row["cap_minor"],
                flags=_flags(row),
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
            )
        )
    adjustments: dict[UUID, list[Adjustment]] = {}
    pending: set[UUID] = set()
    for row in session.execute(
        text("""
            SELECT id, user_id, kind, amount_minor, note, status, taxable,
                   social_security_liable, pension_base
            FROM app.pay_adjustments WHERE tenant_id = :tenant AND period = :first
            ORDER BY created_at, id
        """),
        {"tenant": tenant_id, "first": first},
    ).mappings():
        if row["status"] == "proposed":
            pending.add(row["user_id"])
        elif row["status"] == "approved":
            adjustments.setdefault(row["user_id"], []).append(
                Adjustment(
                    id=str(row["id"]),
                    kind=row["kind"],
                    amount_minor=row["amount_minor"],
                    note=row["note"],
                    flags=_flags(row),
                )
            )
    approved_hours = set(
        session.execute(
            text("SELECT user_id FROM app.time_clock_approvals WHERE month = :first"),
            {"first": first},
        ).scalars()
    )
    signed_101 = set(
        session.execute(
            text("""
                SELECT user_id FROM app.form101_forms
                WHERE tax_year = :year AND status = 'submitted'
            """),
            {"year": first.year},
        ).scalars()
    )
    typed_inputs = {
        row[0]: (row[1] or {}).get("typed", {})
        for row in session.execute(
            text("""
                SELECT l.user_id, l.inputs FROM app.payroll_run_lines l
                JOIN app.payroll_runs r ON r.id = l.run_id WHERE r.period = :first
            """),
            {"first": first},
        )
    }

    built: list[Built] = []
    for person in people:
        terms = Terms(
            employment_type=person["employment_type"],
            monthly_amount_minor=person["monthly_amount_minor"],
            hourly_rate_minor=person["hourly_rate_minor"],
            scope_pct=Decimal(person["scope_pct"]),
        )
        clocked = terms.employment_type in ("hourly", "global_overtime")
        breakdown, open_clocks = _worked(session, person["user_id"], start, end, time_zone, rules)
        work_days = (
            len(breakdown.days) if clocked else _calendar_days(first, person["work_days_per_week"])
        )
        typed = {key: int(value) for key, value in typed_inputs.get(person["user_id"], {}).items()}
        gross = compute_gross(
            terms,
            breakdown if clocked else Breakdown(),
            work_days,
            components.get(person["user_id"], []),
            adjustments.get(person["user_id"], []),
            rules,
            first,
            last,
            typed,
        )
        line = Built(
            person["user_id"], person["role"], person["full_name"] or person["email"], gross
        )
        line.hours, line.work_days, line.employment_type = (
            breakdown,
            work_days,
            terms.employment_type,
        )
        line.problems = list(gross.problems)
        if clocked and person["user_id"] not in approved_hours:
            line.problems.append("hours_not_approved")
        if open_clocks:
            line.problems.append("open_clock")
        if person["user_id"] in pending:
            line.problems.append("pending_adjustments")
        if person["user_id"] not in signed_101:
            line.problems.append("no_form101")
        if not person["bank_last4"]:
            line.problems.append("no_bank")
        if clocked and breakdown.total == 0 and terms.employment_type == "hourly":
            line.problems.append("no_hours")
        if person["start_date"] and person["start_date"] > first:
            line.problems.append("partial_month")
        if (
            terms.employment_type == "hourly"
            and terms.hourly_rate_minor is not None
            and min_hourly is not None
            and terms.hourly_rate_minor < min_hourly
        ) or (
            terms.employment_type != "hourly"
            and terms.monthly_amount_minor is not None
            and min_monthly is not None
            and min_monthly > terms.monthly_amount_minor
        ):
            line.problems.append("below_min_wage")
        built.append(line)

    covered = {person["user_id"] for person in people}
    outside = (
        session.execute(
            text("""
            SELECT DISTINCT coalesce(u.full_name, u.email) AS name
            FROM app.time_clock_entries e
            JOIN app.users u ON u.id = e.user_id
            WHERE e.tenant_id = :tenant AND e.clock_in >= :start AND e.clock_in < :end
              AND e.user_id <> ALL(CAST(:covered AS uuid[]))
        """),
            {"tenant": tenant_id, "start": start, "end": end, "covered": list(covered)},
        )
        .scalars()
        .all()
    )
    notes = [RunNote(code="no_payroll_file", names=sorted(outside))] if outside else []
    return built, notes


def _warning(key: str, acknowledged: set[str]) -> RunWarning:
    code, _, ref = key.partition(":")
    return RunWarning(
        key=key,
        code=code,
        ref=UUID(ref) if ref else None,
        severity="error" if code in ERRORS else "warning",
        acknowledged=key in acknowledged and code not in ERRORS,
    )


def _save(session: Session, tenant_id: UUID, run_id: UUID, built: list[Built]) -> None:
    """Writes the lines, keeping what was typed in and acknowledged for warnings that remain."""
    old = {
        row["user_id"]: row["inputs"]
        for row in session.execute(
            text("SELECT user_id, inputs FROM app.payroll_run_lines WHERE run_id = :run"),
            {"run": run_id},
        ).mappings()
    }
    keep = [line.user_id for line in built]
    session.execute(
        text("DELETE FROM app.payroll_run_lines WHERE run_id = :run AND user_id <> ALL(:keep)"),
        {"run": run_id, "keep": keep},
    )
    for line in built:
        inputs = old.get(line.user_id) or {}
        acknowledged = {
            key: value
            for key, value in (inputs.get("acknowledged") or {}).items()
            if key in line.problems
        }
        gross = line.gross
        session.execute(
            text("""
                INSERT INTO app.payroll_run_lines
                    (tenant_id, run_id, user_id, employment_type, hours_total, hours_regular,
                     hours_tier1, hours_tier2, hours_rest_day, work_days, base_minor,
                     overtime_minor, components_minor, adjustments_minor, deductions_minor,
                     gross_minor, taxable_minor, social_security_minor, pension_base_minor,
                     items, warnings, inputs)
                VALUES (:tenant, :run, :user, :type, :total, :regular, :tier1, :tier2, :rest,
                        :days, :base, :overtime, :components, :adjustments, :deductions, :gross,
                        :taxable, :ss, :pension, CAST(:items AS jsonb), CAST(:warnings AS jsonb),
                        CAST(:inputs AS jsonb))
                ON CONFLICT (run_id, user_id) DO UPDATE SET
                    employment_type = excluded.employment_type,
                    hours_total = excluded.hours_total, hours_regular = excluded.hours_regular,
                    hours_tier1 = excluded.hours_tier1, hours_tier2 = excluded.hours_tier2,
                    hours_rest_day = excluded.hours_rest_day, work_days = excluded.work_days,
                    base_minor = excluded.base_minor, overtime_minor = excluded.overtime_minor,
                    components_minor = excluded.components_minor,
                    adjustments_minor = excluded.adjustments_minor,
                    deductions_minor = excluded.deductions_minor,
                    gross_minor = excluded.gross_minor, taxable_minor = excluded.taxable_minor,
                    social_security_minor = excluded.social_security_minor,
                    pension_base_minor = excluded.pension_base_minor, items = excluded.items,
                    warnings = excluded.warnings, inputs = excluded.inputs, updated_at = now()
            """),
            {
                "tenant": tenant_id,
                "run": run_id,
                "user": line.user_id,
                "type": line.employment_type,
                "total": line.hours.total,
                "regular": line.hours.regular,
                "tier1": line.hours.tier1,
                "tier2": line.hours.tier2,
                "rest": line.hours.rest_day,
                "days": line.work_days,
                "base": gross.base_minor,
                "overtime": gross.overtime_minor,
                "components": gross.components_minor,
                "adjustments": gross.adjustments_minor,
                "deductions": gross.deductions_minor,
                "gross": gross.gross_minor,
                "taxable": gross.taxable_minor,
                "ss": gross.social_security_minor,
                "pension": gross.pension_base_minor,
                "items": json.dumps([item.as_dict() for item in gross.items]),
                "warnings": json.dumps(line.problems),
                "inputs": json.dumps(
                    {"typed": inputs.get("typed") or {}, "acknowledged": acknowledged}
                ),
            },
        )


def _refresh(session: Session, tenant_id: UUID, run_id: UUID, first: dt.date) -> list[RunNote]:
    built, notes = _build(session, tenant_id, first)
    _save(session, tenant_id, run_id, built)
    session.execute(
        text("UPDATE app.payroll_runs SET updated_at = now() WHERE id = :id"), {"id": run_id}
    )
    return notes


# -- reading -------------------------------------------------------------------------------------


def _run_row(session: Session, first: dt.date) -> Any:
    row = (
        session.execute(
            text("SELECT * FROM app.payroll_runs WHERE period = :first"), {"first": first}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return row


def _lines(context: TenantContext, run_id: UUID) -> list[RunLine]:
    rows = context.session.execute(
        text("""
            SELECT l.*, coalesce(u.full_name, u.email) AS full_name, m.role
            FROM app.payroll_run_lines l
            JOIN app.users u ON u.id = l.user_id
            JOIN app.tenant_members m ON m.tenant_id = l.tenant_id AND m.user_id = l.user_id
            WHERE l.run_id = :run ORDER BY coalesce(u.full_name, u.email), l.user_id
        """),
        {"run": run_id},
    ).mappings()
    result = []
    for row in rows:
        if not _below(context, row["role"]):
            continue
        acknowledged = set((row["inputs"] or {}).get("acknowledged", {}))
        warnings = [_warning(key, acknowledged) for key in row["warnings"]]
        result.append(
            RunLine(
                user_id=row["user_id"],
                full_name=row["full_name"],
                employment_type=row["employment_type"],
                hours=Hours(
                    total=float(row["hours_total"]),
                    regular=float(row["hours_regular"]),
                    tier1=float(row["hours_tier1"]),
                    tier2=float(row["hours_tier2"]),
                    rest_day=float(row["hours_rest_day"]),
                ),
                work_days=row["work_days"],
                base_minor=row["base_minor"],
                overtime_minor=row["overtime_minor"],
                components_minor=row["components_minor"],
                adjustments_minor=row["adjustments_minor"],
                deductions_minor=row["deductions_minor"],
                gross_minor=row["gross_minor"],
                taxable_minor=row["taxable_minor"],
                social_security_minor=row["social_security_minor"],
                pension_base_minor=row["pension_base_minor"],
                items=[RunItem.model_validate(item) for item in row["items"]],
                warnings=warnings,
                typed={UUID(k): int(v) for k, v in (row["inputs"] or {}).get("typed", {}).items()},
                ready=all(w.acknowledged for w in warnings),
            )
        )
    return result


def _present(context: TenantContext, first: dt.date, notes: list[RunNote] | None = None) -> Run:
    row = _run_row(context.session, first)
    lines = _lines(context, row["id"])
    previous = context.session.execute(
        text("""
            SELECT sum(l.gross_minor) FROM app.payroll_run_lines l
            JOIN app.payroll_runs r ON r.id = l.run_id
            WHERE r.period = (CAST(:first AS date) - interval '1 month')::date
        """),
        {"first": first},
    ).scalar()
    return Run(
        period=row["period"],
        stage=row["stage"],
        currency=row["currency"],
        payslips_draft=row["accountant_checked_at"] is None,
        approved_at=row["approved_at"],
        accountant_checked_at=row["accountant_checked_at"],
        summary=RunSummary(
            people=len(lines),
            gross_minor=sum(line.gross_minor for line in lines),
            deductions_minor=sum(line.deductions_minor for line in lines),
            previous_gross_minor=int(previous) if previous is not None else None,
            open_errors=sum(w.severity == "error" for line in lines for w in line.warnings),
            open_warnings=sum(
                w.severity == "warning" and not w.acknowledged
                for line in lines
                for w in line.warnings
            ),
        ),
        notes=notes if notes is not None else [],
        lines=lines,
    )


@router.get("/payroll/runs")
def list_payroll_runs(context: ReadDep) -> list[RunRow]:
    """The last two years of runs, newest first (everyone's lines add up here)."""
    _ensure_unscoped(context)
    rows = context.session.execute(
        text("""
            SELECT r.period, r.stage, coalesce(sum(l.gross_minor), 0)::bigint AS gross_minor,
                   count(l.id) AS people
            FROM app.payroll_runs r LEFT JOIN app.payroll_run_lines l ON l.run_id = r.id
            GROUP BY r.id ORDER BY r.period DESC LIMIT 24
        """)
    ).mappings()
    return [RunRow.model_validate(dict(row)) for row in rows]


@router.get("/payroll/runs/{period}")
def get_payroll_run(period: PeriodPath, context: ReadDep) -> Run:
    _ensure_unscoped(context)
    first = _first(period)
    _run_row(context.session, first)
    return _present(context, first)


# -- changing ------------------------------------------------------------------------------------


@router.post("/payroll/runs", status_code=status.HTTP_201_CREATED)
def create_payroll_run(body: RunCreate, context: ManageDep, user: UserDep) -> Run:
    """Starts the month's run (once) and works out everyone's lines."""
    _ensure_unscoped(context)
    first = _first(body.period)
    if first > dt.date.today().replace(day=1) + dt.timedelta(days=32):
        raise _unprocessable("period_in_future")
    session = context.session
    currency = session.execute(
        text("SELECT currency FROM app.tenants WHERE id = :t"), {"t": context.tenant_id}
    ).scalar_one()
    run_id = session.execute(
        text("""
            INSERT INTO app.payroll_runs (tenant_id, period, currency, created_by)
            VALUES (:tenant, :first, :currency, :user)
            ON CONFLICT (tenant_id, period) DO NOTHING RETURNING id
        """),
        {"tenant": context.tenant_id, "first": first, "currency": currency, "user": user.id},
    ).scalar()
    if run_id is None:
        raise _conflict("run_exists")
    notes = _refresh(session, context.tenant_id, run_id, first)
    _audit(
        session, context.tenant_id, "payroll.run_created", "payroll_run", run_id, period=str(first)
    )
    return _present(context, first, notes)


def _editable(session: Session, first: dt.date) -> Any:
    row = _run_row(session, first)
    if row["stage"] == "approved":
        raise _conflict("run_approved")
    return row


@router.post("/payroll/runs/{period}/refresh")
def refresh_payroll_run(period: PeriodPath, context: ManageDep) -> Run:
    """Works the lines out again from the latest hours, components and one-off amounts."""
    _ensure_unscoped(context)
    first = _first(period)
    row = _editable(context.session, first)
    notes = _refresh(context.session, context.tenant_id, row["id"], first)
    return _present(context, first, notes)


def _line(context: TenantContext, run_id: UUID, user_id: UUID) -> Any:
    line = (
        context.session.execute(
            text("""
                SELECT l.*, m.role FROM app.payroll_run_lines l
                JOIN app.tenant_members m ON m.tenant_id = l.tenant_id AND m.user_id = l.user_id
                WHERE l.run_id = :run AND l.user_id = :user
            """),
            {"run": run_id, "user": user_id},
        )
        .mappings()
        .first()
    )
    if line is None or not _below(context, line["role"]):
        raise not_found()
    return line


@router.put("/payroll/runs/{period}/lines/{user_id}/typed")
def type_payroll_amount(
    period: PeriodPath, user_id: UUID, body: TypedAmount, context: ManageDep
) -> Run:
    """Types in the amount of a component for this month (counted "by month", or without an
    automatic rate yet). Only for the person's own active components."""
    _ensure_unscoped(context)
    first = _first(period)
    run = _editable(context.session, first)
    line = _line(context, run["id"], user_id)
    owned = context.session.execute(
        text("SELECT 1 FROM app.pay_components WHERE id = :id AND user_id = :user"),
        {"id": body.component_id, "user": user_id},
    ).first()
    if owned is None:
        raise not_found()
    inputs = dict(line["inputs"] or {})
    typed = dict(inputs.get("typed") or {})
    if body.amount_minor is None:
        typed.pop(str(body.component_id), None)
    else:
        typed[str(body.component_id)] = body.amount_minor
    inputs["typed"] = typed
    context.session.execute(
        text("UPDATE app.payroll_run_lines SET inputs = CAST(:inputs AS jsonb) WHERE id = :id"),
        {"inputs": json.dumps(inputs), "id": line["id"]},
    )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.amount_typed",
        "member",
        user_id,
        period=str(first),
        component_id=body.component_id,
        amount_minor=body.amount_minor,
    )
    notes = _refresh(context.session, context.tenant_id, run["id"], first)
    return _present(context, first, notes)


@router.post("/payroll/runs/{period}/lines/{user_id}/acknowledge")
def acknowledge_payroll_warning(
    period: PeriodPath, user_id: UUID, body: Acknowledge, context: ManageDep
) -> Run:
    """Marks a warning as seen and accepted (errors cannot be acknowledged: they must be fixed)."""
    _ensure_unscoped(context)
    first = _first(period)
    run = _editable(context.session, first)
    line = _line(context, run["id"], user_id)
    if body.key not in line["warnings"]:
        raise not_found()
    if body.key.partition(":")[0] in ERRORS:
        raise _unprocessable("cannot_acknowledge")
    inputs = dict(line["inputs"] or {})
    acknowledged = dict(inputs.get("acknowledged") or {})
    if body.acknowledged:
        acknowledged[body.key] = {
            "by": str(context.session.execute(text("SELECT app.current_user_id()")).scalar_one())
        }
    else:
        acknowledged.pop(body.key, None)
    inputs["acknowledged"] = acknowledged
    context.session.execute(
        text("UPDATE app.payroll_run_lines SET inputs = CAST(:inputs AS jsonb) WHERE id = :id"),
        {"inputs": json.dumps(inputs), "id": line["id"]},
    )
    _audit(
        context.session,
        context.tenant_id,
        "payroll.warning_acknowledged",
        "member",
        user_id,
        period=str(first),
        key=body.key,
        acknowledged=body.acknowledged,
    )
    return _present(context, first)


def _problems(session: Session, run_id: UUID) -> list[tuple[str, bool]]:
    """(code, acknowledged) of every warning of every line of the run."""
    result = []
    for warnings, inputs in session.execute(
        text("SELECT warnings, inputs FROM app.payroll_run_lines WHERE run_id = :run"),
        {"run": run_id},
    ):
        acknowledged = set((inputs or {}).get("acknowledged", {}))
        result += [(key.partition(":")[0], key in acknowledged) for key in warnings]
    return result


@router.post("/payroll/runs/{period}/stage")
def move_payroll_stage(
    period: PeriodPath, body: StageBody, context: ManageDep, user: UserDep
) -> Run:
    """Moves the run one stage forward (checked) or back (until it is approved). Approving is for
    the owner only and locks the month."""
    _ensure_unscoped(context)
    first = _first(period)
    session = context.session
    run = _editable(session, first)
    current, target = STAGES.index(run["stage"]), STAGES.index(body.stage)
    if target == current:
        return _present(context, first)
    if target > current + 1:
        raise _unprocessable("one_stage_at_a_time")
    if target == 3 and Permission.PAYROLL_APPROVE not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if target < current:
        session.execute(
            text("""
                UPDATE app.payroll_runs SET stage = :stage, updated_at = now(),
                    hours_locked_at = CASE WHEN :stage = 'hours' THEN NULL ELSE hours_locked_at END,
                    hours_locked_by = CASE WHEN :stage = 'hours' THEN NULL ELSE hours_locked_by END,
                    reviewed_at = NULL, reviewed_by = NULL
                WHERE id = :id
            """),
            {"stage": body.stage, "id": run["id"]},
        )
        _audit(
            session,
            context.tenant_id,
            "payroll.run_stage",
            "payroll_run",
            run["id"],
            stage=body.stage,
        )
        return _present(context, first)
    notes = _refresh(session, context.tenant_id, run["id"], first)
    problems = _problems(session, run["id"])
    leaving = STAGES[current]
    if any(code in BLOCKS[leaving] for code, _ in problems):
        raise _conflict("run_blocked")
    if target == 3 and any(code not in ERRORS and not done for code, done in problems):
        raise _conflict("warnings_open")
    session.execute(
        text("""
            UPDATE app.payroll_runs SET stage = :stage, updated_at = now(),
                hours_locked_at = CASE WHEN :stage = 'additions'
                    THEN now() ELSE hours_locked_at END,
                hours_locked_by = CASE WHEN :stage = 'additions'
                    THEN :user ELSE hours_locked_by END,
                reviewed_at = CASE WHEN :stage = 'review' THEN now() ELSE reviewed_at END,
                reviewed_by = CASE WHEN :stage = 'review' THEN :user ELSE reviewed_by END,
                approved_at = CASE WHEN :stage = 'approved' THEN now() END,
                approved_by = CASE WHEN :stage = 'approved' THEN :user END
            WHERE id = :id
        """),
        {"stage": body.stage, "user": user.id, "id": run["id"]},
    )
    if body.stage == "approved":
        from app.api.payslips import file_payslips, freeze_net

        freeze_net(session, context.tenant_id, run)
        _store_export(context, run["id"], first)
        file_payslips(session, context.tenant_id, _run_row(session, first))
    _audit(
        session, context.tenant_id, "payroll.run_stage", "payroll_run", run["id"], stage=body.stage
    )
    return _present(context, first, notes)


@router.post("/payroll/runs/{period}/accountant-check", status_code=status.HTTP_204_NO_CONTENT)
def payroll_accountant_check(period: PeriodPath, context: ApproveDep, user: UserDep) -> None:
    """The owner records that an accountant checked the approved run; payslips stop being drafts."""
    _ensure_unscoped(context)
    first = _first(period)
    run = _run_row(context.session, first)
    if run["stage"] != "approved":
        raise _conflict("run_not_approved")
    context.session.execute(
        text("""
            UPDATE app.payroll_runs
            SET accountant_checked_at = now(), accountant_checked_by = :user WHERE id = :id
        """),
        {"user": user.id, "id": run["id"]},
    )
    from app.api.payslips import file_payslips

    file_payslips(context.session, context.tenant_id, _run_row(context.session, first), final=True)
    _audit(
        context.session, context.tenant_id, "payroll.accountant_checked", "payroll_run", run["id"]
    )


# -- the accountant export -----------------------------------------------------------------------

KINDS = ("travel", "meals", "phone", "car", "fixed_addition", "recuperation")
ADJUSTMENT_KINDS = ("bonus", "holiday_gift", "expense_refund")


def _export_rows(
    context: TenantContext, run_id: UUID, currency: str
) -> tuple[list[str], list[list]]:
    """One row per person with every component, hours and totals (money in major units)."""
    major = Decimal(100)
    header = [
        "employee",
        "employment_type",
        "hours_total",
        "hours_regular",
        "hours_overtime_125",
        "hours_overtime_150",
        "hours_rest_day",
        "work_days",
        "base",
        "overtime",
        *KINDS,
        *ADJUSTMENT_KINDS,
        "deductions",
        "gross",
        "taxable",
        "social_security_liable",
        "pension_base",
        "currency",
        "open_warnings",
    ]
    rows = []
    for line in _lines(context, run_id):
        per_kind: dict[str, int] = {}
        for item in line.items:
            if item.section in ("component", "adjustment"):
                per_kind[item.code] = per_kind.get(item.code, 0) + item.amount_minor
        rows.append(
            [
                line.full_name,
                line.employment_type,
                line.hours.total,
                line.hours.regular,
                line.hours.tier1,
                line.hours.tier2,
                line.hours.rest_day,
                line.work_days,
                Decimal(line.base_minor) / major,
                Decimal(line.overtime_minor) / major,
                *[Decimal(per_kind.get(code, 0)) / major for code in (*KINDS, *ADJUSTMENT_KINDS)],
                Decimal(line.deductions_minor) / major,
                Decimal(line.gross_minor) / major,
                Decimal(line.taxable_minor) / major,
                Decimal(line.social_security_minor) / major,
                Decimal(line.pension_base_minor) / major,
                currency,
                sum(1 for w in line.warnings if not w.acknowledged),
            ]
        )
    return header, rows


def _csv(header: list[str], rows: list[list]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + out.getvalue().encode()  # a byte order mark so Excel reads Hebrew


def _xlsx(header: list[str], rows: list[list]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(header)
    for row in rows:
        sheet.append([float(cell) if isinstance(cell, Decimal) else cell for cell in row])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _store_export(context: TenantContext, run_id: UUID, first: dt.date) -> None:
    """Keeps the approved run's workbook in the payroll folder of the files area. A full storage
    never stops the approval: the export can always be downloaded again."""
    currency = _run_row(context.session, first)["currency"]
    header, rows = _export_rows(context, run_id, currency)
    try:
        with context.session.begin_nested():
            folder = system_folder_id(context.session, context.tenant_id, "payroll")
            saved = store_file(
                context.session,
                context.tenant_id,
                folder,
                name=f"payroll-{first:%Y-%m}.xlsx",
                content=_xlsx(header, rows),
                content_type=XLSX,
            )
            context.session.execute(
                text("UPDATE app.payroll_runs SET export_file_id = :file WHERE id = :id"),
                {"file": saved["id"], "id": run_id},
            )
    except HTTPException:
        return


@router.get("/payroll/runs/{period}/export")
def export_payroll_run(
    period: PeriodPath,
    context: ReadDep,
    file_format: Annotated[Literal["csv", "xlsx"], Query(alias="format")] = "xlsx",
) -> Response:
    """The month for the accountant: a neutral table, a row per person (payslips marked draft until
    an accountant checks the run)."""
    _ensure_unscoped(context)
    first = _first(period)
    run = _run_row(context.session, first)
    header, rows = _export_rows(context, run["id"], run["currency"])
    _audit(
        context.session,
        context.tenant_id,
        "payroll.exported",
        "payroll_run",
        run["id"],
        format=file_format,
    )
    if file_format == "csv":
        body, kind = _csv(header, rows), "text/csv; charset=utf-8"
    else:
        body, kind = _xlsx(header, rows), XLSX
    return Response(
        content=body,
        media_type=kind,
        headers={
            "Content-Disposition": f'attachment; filename="payroll-{first:%Y-%m}.{file_format}"'
        },
    )
