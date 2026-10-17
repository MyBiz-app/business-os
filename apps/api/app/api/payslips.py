"""Net pay, payslips and the bank file of a payroll run (round 6, P5).

The gross lines of a run (P4) are turned into net pay by `app.payroll.net` from the dated rates
table, the person's credit points (Form 101), pension and study fund. Until the run is approved the
net is worked out on every request; approving freezes it in the line, so an approved month never
changes when the rates table does. Payslips are marked "draft for the accountant" until the owner
records that an accountant checked the run. The bank file (Masav) is only generated for an
approved month and only for the owner; nothing is ever sent to a bank."""

import datetime as dt
import json
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, TenantDep, UserDep, require
from app.api.pay_components import _audit, _below
from app.api.payroll_runs import (
    PeriodPath,
    _conflict,
    _ensure_unscoped,
    _first,
    _rates,
    _run_row,
)
from app.core import identity
from app.core.permissions import Permission
from app.documents import render
from app.files import store_file, system_folder_id
from app.payroll import masav
from app.payroll.net import Funds, Net, compute_net
from app.payroll.rates import Rates, resolve
from app.providers import secrets

router = APIRouter(tags=["payroll"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_READ))]
ApproveDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_APPROVE))]
PDF_RESPONSES: dict[int | str, dict[str, Any]] = {200: {"content": {"application/pdf": {}}}}


class NetLine(BaseModel):
    code: str
    amount_minor: int
    base_minor: int | None
    percent: str | None


class PersonNet(BaseModel):
    user_id: UUID
    full_name: str | None
    gross_minor: int
    total_deductions_minor: int
    net_minor: int
    credit_points: str
    deductions: list[NetLine]
    employer: list[NetLine]
    problems: list[str]
    frozen: bool = Field(description="Worked out when the run was approved")


class RunNet(BaseModel):
    period: dt.date
    currency: str
    payslips_draft: bool
    example_rates: list[str] = Field(
        description="Rates that came from the built-in examples, not from the rates table"
    )
    net_minor: int
    people: list[PersonNet]


class PayslipRow(BaseModel):
    period: dt.date
    net_minor: int
    currency: str
    draft: bool


class BankFileBody(BaseModel):
    institution_code: str = Field(pattern=r"^\d{1,8}$", description="Masav institution code")
    sending_code: str = Field(pattern=r"^\d{1,5}$")
    institution_name: str = Field(min_length=1, max_length=30)
    pay_date: dt.date


def _pdf(content: bytes, name: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# -- working the net out ------------------------------------------------------------------------


def _percent(value: Any, fallback: Decimal) -> Decimal:
    return Decimal(str(value)) if value is not None else fallback


def _funds(profile: Any, rates: Rates) -> Funds:
    pension = (profile["pension"] if profile else None) or {}
    study = (profile["study_fund"] if profile else None) or {}
    return Funds(
        pension_employee_pct=_percent(pension.get("employee_pct"), rates.pension_employee_pct),
        pension_employer_pct=_percent(pension.get("employer_pct"), rates.pension_employer_pct),
        severance_pct=_percent(pension.get("severance_pct"), rates.severance_pct),
        study_employee_pct=_percent(study.get("employee_pct"), Decimal(0)),
        study_employer_pct=_percent(study.get("employer_pct"), Decimal(0)),
    )


def _credit_points(session: Session, user_id: UUID, year: int) -> Decimal:
    row = (
        session.execute(
            text("""
                SELECT coalesce(credit_points_override, credit_points) AS points
                FROM app.form101_forms
                WHERE user_id = :user AND tax_year = :year AND status = 'submitted'
            """),
            {"user": user_id, "year": year},
        )
        .mappings()
        .first()
    )
    return Decimal(row["points"]) if row and row["points"] is not None else Decimal(0)


def _profiles(session: Session, tenant_id: UUID) -> dict[UUID, Any]:
    rows = session.execute(
        text("SELECT user_id, pension, study_fund FROM app.employment_profiles"),
    ).mappings()
    return {row["user_id"]: row for row in rows}


def _net_of(session: Session, line: Any, profile: Any, rates: Rates, year: int) -> Net:
    return compute_net(
        line["gross_minor"],
        line["taxable_minor"],
        line["social_security_minor"],
        line["pension_base_minor"],
        line["deductions_minor"],
        _credit_points(session, line["user_id"], year),
        _funds(profile, rates),
        rates,
    )


def _line_rows(session: Session, run_id: UUID) -> list[Any]:
    return list(
        session.execute(
            text("""
                SELECT l.*, coalesce(u.full_name, u.email) AS full_name, m.role
                FROM app.payroll_run_lines l
                JOIN app.users u ON u.id = l.user_id
                JOIN app.tenant_members m ON m.tenant_id = l.tenant_id AND m.user_id = l.user_id
                WHERE l.run_id = :run ORDER BY coalesce(u.full_name, u.email), l.user_id
            """),
            {"run": run_id},
        ).mappings()
    )


def _all_nets(session: Session, tenant_id: UUID, run: Any) -> dict[UUID, tuple[dict, bool]]:
    """The net of every line: the frozen one when the month is approved, else worked out now."""
    rates = resolve(_rates(session, run["period"]))
    profiles = _profiles(session, tenant_id)
    nets: dict[UUID, tuple[dict, bool]] = {}
    for line in _line_rows(session, run["id"]):
        frozen = (line["inputs"] or {}).get("net")
        if frozen is not None:
            nets[line["user_id"]] = (frozen, True)
        else:
            net = _net_of(session, line, profiles.get(line["user_id"]), rates, run["period"].year)
            nets[line["user_id"]] = (net.as_dict(), False)
    return nets


def freeze_net(session: Session, tenant_id: UUID, run: Any) -> None:
    """Called when a run is approved: the net of every line is kept in the line."""
    for user_id, (net, frozen) in _all_nets(session, tenant_id, run).items():
        if frozen:
            continue
        session.execute(
            text("""
                UPDATE app.payroll_run_lines
                SET inputs = jsonb_set(coalesce(inputs, '{}'::jsonb), '{net}', CAST(:net AS jsonb))
                WHERE run_id = :run AND user_id = :user
            """),
            {"net": json.dumps(net), "run": run["id"], "user": user_id},
        )


def _example_keys(session: Session, first: dt.date) -> list[str]:
    return list(resolve(_rates(session, first)).example_keys)


# -- the net of a month -------------------------------------------------------------------------


@router.get("/payroll/runs/{period}/net")
def get_run_net(period: PeriodPath, context: ReadDep) -> RunNet:
    """Net pay of everyone the reader may see, with the deductions it came from."""
    _ensure_unscoped(context)
    first = _first(period)
    session = context.session
    run = _run_row(session, first)
    nets = _all_nets(session, context.tenant_id, run)
    people = []
    for line in _line_rows(session, run["id"]):
        if not _below(context, line["role"]):
            continue
        net, frozen = nets[line["user_id"]]
        people.append(
            PersonNet(
                user_id=line["user_id"],
                full_name=line["full_name"],
                gross_minor=net["gross_minor"],
                total_deductions_minor=net["total_deductions_minor"],
                net_minor=net["net_minor"],
                credit_points=net["credit_points"],
                deductions=[NetLine(**d) for d in net["deductions"]],
                employer=[NetLine(**d) for d in net["employer"]],
                problems=net["problems"],
                frozen=frozen,
            )
        )
    return RunNet(
        period=run["period"],
        currency=run["currency"],
        payslips_draft=run["accountant_checked_at"] is None,
        example_rates=_example_keys(session, first),
        net_minor=sum(person.net_minor for person in people),
        people=people,
    )


# -- the payslip --------------------------------------------------------------------------------


def _year_to_date(session: Session, user_id: UUID, run: Any, net: dict) -> dict[str, int]:
    """Gross and deductions of the tax year up to and including this month. Earlier months count
    from their frozen net; a month nobody approved has none and counts its gross only."""
    rows = session.execute(
        text("""
            SELECT l.gross_minor, l.inputs -> 'net' AS net
            FROM app.payroll_run_lines l JOIN app.payroll_runs r ON r.id = l.run_id
            WHERE l.user_id = :user AND r.period < :period
              AND r.period >= make_date(CAST(:year AS int), 1, 1)
        """),
        {"user": user_id, "period": run["period"], "year": run["period"].year},
    ).mappings()
    totals = {
        "gross": net["gross_minor"],
        "tax": net["tax_minor"],
        "national_insurance": net["national_insurance_minor"],
        "health": net["health_minor"],
    }
    for row in rows:
        totals["gross"] += row["gross_minor"]
        if row["net"]:
            totals["tax"] += row["net"]["tax_minor"]
            totals["national_insurance"] += row["net"]["national_insurance_minor"]
            totals["health"] += row["net"]["health_minor"]
    return totals


def payslip_pdf(session: Session, tenant_id: UUID, run: Any, user_id: UUID) -> bytes:
    line = next((row for row in _line_rows(session, run["id"]) if row["user_id"] == user_id), None)
    if line is None:
        raise not_found()
    net = _all_nets(session, tenant_id, run)[user_id][0]
    tenant = (
        session.execute(
            text("""
                SELECT name, locale, time_zone, primary_color, logo, logo_content_type,
                       address_line, address_city, business_number
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    profile = (
        session.execute(
            text("""
                SELECT job_title, start_date, bank_last4, work_days_per_week
                FROM app.employment_profiles WHERE user_id = :user
            """),
            {"user": user_id},
        )
        .mappings()
        .first()
    )
    identity_row = (
        session.execute(
            text("SELECT id_last4 FROM app.person_identities WHERE user_id = :user"),
            {"user": user_id},
        )
        .mappings()
        .first()
    )
    lang = render.language(tenant["locale"])
    t = render.texts(lang)
    currency = run["currency"]

    def money(amount: int) -> str:
        return render.money(amount, currency, lang)

    def label(item: dict) -> str:
        translated = t["payslipItems"].get(item["code"], item["label"])
        if item["section"] == "component" or item["label"] != item["code"]:
            return item["label"]
        return f"{translated} {item['percent']}%" if item["section"] == "overtime" else translated

    payments = [
        {
            "label": label(item),
            "quantity": item["quantity"],
            "rate": money(item["unit_minor"]) if item["unit_minor"] else "",
            "amount": money(item["amount_minor"]),
        }
        for item in line["items"]
        if item["section"] != "deduction"
    ]
    deductions = [
        {
            "label": t["payslipDeductions"][d["code"]]
            + (f" {d['percent']}%" if d.get("percent") else ""),
            "amount": money(d["amount_minor"]),
        }
        for d in net["deductions"]
    ]
    employer = [
        {"label": t["payslipEmployer"][d["code"]], "amount": money(d["amount_minor"])}
        for d in net["employer"]
    ]
    ytd = _year_to_date(session, user_id, run, net)
    draft = run["accountant_checked_at"] is None
    logo = (
        render.data_uri(bytes(tenant["logo"]), tenant["logo_content_type"])
        if tenant["logo"] and tenant["logo_content_type"]
        else None
    )
    first = run["period"]
    issuer_lines = [
        ", ".join(p for p in (tenant["address_line"], tenant["address_city"]) if p),
        f"{t['businessNumber']} {tenant['business_number']}" if tenant["business_number"] else "",
    ]
    return render.render_pdf(
        "payslip",
        lang,
        {
            "accent": render.accent(tenant["primary_color"]),
            "issuer": {
                "name": tenant["name"],
                "logo": logo,
                "lines": [part for part in issuer_lines if part],
            },
            "doc_title": render.fill(t["payslip"], month=f"{first.month:02d}/{first.year}"),
            "doc_number": "",
            "sample_note": None,
            "watermark": t["payslipDraft"] if draft else None,
            "draft_note": t["payslipDraft"] if draft else None,
            "footer_right": "",
            "employee": line["full_name"],
            "id_last4": identity_row["id_last4"] if identity_row else None,
            "job_title": profile["job_title"] if profile else None,
            "start": render.day(profile["start_date"], lang)
            if profile and profile["start_date"]
            else None,
            "bank_last4": profile["bank_last4"] if profile else None,
            "credit_points": net["credit_points"],
            "hours": float(line["hours_total"]) or None,
            "work_days": line["work_days"],
            "payments": payments,
            "total_payments": money(net["gross_minor"]),
            "deductions": deductions,
            "total_deductions": money(net["total_deductions_minor"]),
            "net": money(net["net_minor"]),
            "employer": employer,
            "ytd": {key: money(value) for key, value in ytd.items()},
        },
    )


def _visible_run(context: TenantContext, period: str) -> Any:
    _ensure_unscoped(context)
    return _run_row(context.session, _first(period))


@router.get(
    "/payroll/runs/{period}/payslips/{user_id}/pdf",
    response_class=Response,
    responses=PDF_RESPONSES,
)
def payslip_file(period: PeriodPath, user_id: UUID, context: ReadDep) -> Response:
    run = _visible_run(context, period)
    role = context.session.execute(
        text("SELECT role FROM app.tenant_members WHERE user_id = :user"), {"user": user_id}
    ).scalar()
    if role is None or not _below(context, role):
        raise not_found()
    _audit(context.session, context.tenant_id, "payroll.payslip_viewed", "member", user_id)
    return _pdf(payslip_pdf(context.session, context.tenant_id, run, user_id), f"payslip-{period}")


@router.get("/me/payslips")
def my_payslips(context: TenantDep, user: UserDep) -> list[PayslipRow]:
    """The signed-in team member's own approved months, newest first."""
    rows = context.session.execute(
        text("""
            SELECT r.period, r.currency, r.accountant_checked_at, l.inputs -> 'net' AS net
            FROM app.payroll_run_lines l JOIN app.payroll_runs r ON r.id = l.run_id
            WHERE l.user_id = :user AND r.stage = 'approved' ORDER BY r.period DESC
        """),
        {"user": user.id},
    ).mappings()
    return [
        PayslipRow(
            period=row["period"],
            net_minor=row["net"]["net_minor"] if row["net"] else 0,
            currency=row["currency"],
            draft=row["accountant_checked_at"] is None,
        )
        for row in rows
    ]


@router.get("/me/payslips/{period}/pdf", response_class=Response, responses=PDF_RESPONSES)
def my_payslip_file(period: PeriodPath, context: TenantDep, user: UserDep) -> Response:
    run = _run_row(context.session, _first(period))
    if run["stage"] != "approved":
        raise not_found()
    _audit(context.session, context.tenant_id, "payroll.payslip_viewed", "member", user.id)
    return _pdf(payslip_pdf(context.session, context.tenant_id, run, user.id), f"payslip-{period}")


# -- the bank file ------------------------------------------------------------------------------


@router.post("/payroll/runs/{period}/bank-file", response_class=Response)
def bank_file(period: PeriodPath, body: BankFileBody, context: ApproveDep) -> Response:
    """The Masav transfer file of an approved month (net pay of everyone with something to pay).
    It is generated and kept in the payroll folder; it is never sent anywhere."""
    _ensure_unscoped(context)
    first = _first(period)
    session = context.session
    run = _run_row(session, first)
    if run["stage"] != "approved":
        raise _conflict("run_not_approved")
    nets = _all_nets(session, context.tenant_id, run)
    payees: list[masav.Payee] = []
    for line in _line_rows(session, run["id"]):
        amount = nets[line["user_id"]][0]["net_minor"]
        if amount <= 0:
            continue
        found = (
            session.execute(
                text("""
                    SELECT p.bank_encrypted, i.id_number_encrypted
                    FROM app.employment_profiles p
                    LEFT JOIN app.person_identities i ON i.user_id = p.user_id
                    WHERE p.user_id = :user
                """),
                {"user": line["user_id"]},
            )
            .mappings()
            .first()
        )
        if not found or found["bank_encrypted"] is None or found["id_number_encrypted"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="payees_incomplete")
        bank = secrets.decrypt(found["bank_encrypted"])
        payees.append(
            masav.Payee(
                name=line["full_name"] or "",
                id_number=identity.decrypt_number(found["id_number_encrypted"]),
                bank_code=bank["bank_code"],
                branch=bank["branch"],
                account=bank["account"],
                amount_minor=amount,
                reference=f"{first:%Y-%m}",
            )
        )
    if not payees:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="nothing_to_pay")
    content = masav.build(
        masav.Sender(body.institution_code, body.sending_code, body.institution_name),
        body.pay_date,
        dt.date.today(),
        first,
        payees,
    )
    name = f"masav-{first:%Y-%m}.txt"
    try:
        with session.begin_nested():
            store_file(
                session,
                context.tenant_id,
                system_folder_id(session, context.tenant_id, "payroll"),
                name=name,
                content=content,
                content_type="text/plain",
            )
    except HTTPException:
        pass  # a full storage never stops the download
    _audit(
        session,
        context.tenant_id,
        "payroll.bank_file_generated",
        "payroll_run",
        run["id"],
        payees=len(payees),
    )
    return Response(
        content=content,
        media_type="text/plain; charset=cp862",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
