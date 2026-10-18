"""Employment terms and the digital Form 101 (round 6, P1).

Terms (global, hourly, pension, bank) belong to a team member's employment profile; the yearly
tax-credit declaration (Form 101) is requested by a payroll manager, filled and signed by the
employee in the app, and stored encrypted. The server computes the credit points from the
answers (`app.payroll.credit_points`); a payroll manager may overwrite them with a note.

`payroll.read` sees terms and forms (managers within their reach), `payroll.manage` changes them,
and an employee always sees their own. The bank account is revealed only with `identity.read`,
and every reveal and change is written to the audit log."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, TenantDep, UserDep, require
from app.api.staff import _ensure_member_in_reach
from app.core.permissions import Permission
from app.files import keep_copy, safe_name
from app.payroll import credit_points
from app.providers import secrets

router = APIRouter(tags=["payroll"])

PayrollReadDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_READ))]
PayrollManageDep = Annotated[TenantContext, Depends(require(Permission.PAYROLL_MANAGE))]
RevealDep = Annotated[TenantContext, Depends(require(Permission.IDENTITY_READ))]

EmploymentType = Literal["global", "hourly", "global_overtime"]


# Employment terms -----------------------------------------------------------------------------


class Pension(BaseModel):
    fund_name: str | None = Field(default=None, max_length=120)
    employee_pct: Decimal = Field(default=Decimal("6"), ge=0, le=100)
    employer_pct: Decimal = Field(default=Decimal("6.5"), ge=0, le=100)
    severance_pct: Decimal = Field(default=Decimal("6"), ge=0, le=100)


class StudyFund(BaseModel):
    fund_name: str | None = Field(default=None, max_length=120)
    employee_pct: Decimal = Field(default=Decimal("2.5"), ge=0, le=100)
    employer_pct: Decimal = Field(default=Decimal("7.5"), ge=0, le=100)


class BankAccount(BaseModel):
    bank_code: str = Field(pattern=r"^\d{1,3}$")
    branch: str = Field(pattern=r"^\d{1,4}$")
    account: str = Field(pattern=r"^\d{3,12}$")


class EmploymentBody(BaseModel):
    employment_type: EmploymentType = "global"
    currency: str = Field(default="ILS", pattern=r"^[A-Z]{3}$")
    monthly_amount_minor: int | None = Field(default=None, ge=0)
    hourly_rate_minor: int | None = Field(default=None, ge=0)
    scope_pct: Decimal = Field(default=Decimal("100"), gt=0, le=100)
    start_date: date | None = None
    work_days_per_week: int = Field(default=5, ge=1, le=7)
    job_title: str | None = Field(default=None, max_length=120)
    billing_location_id: UUID | None = None
    pension: Pension | None = None
    study_fund: StudyFund | None = None
    employment_notice_date: date | None = None
    bank: BankAccount | None = Field(
        default=None, description="Replaces the stored account; leave out to keep it"
    )

    @field_validator("job_title", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value


class Employment(BaseModel):
    exists: bool
    employment_type: EmploymentType = "global"
    currency: str = "ILS"
    monthly_amount_minor: int | None = None
    hourly_rate_minor: int | None = None
    scope_pct: Decimal = Decimal("100")
    start_date: date | None = None
    work_days_per_week: int = 5
    job_title: str | None = None
    billing_location_id: UUID | None = None
    pension: Pension | None = None
    study_fund: StudyFund | None = None
    employment_notice_date: date | None = None
    bank_last4: str | None = None
    can_reveal_bank: bool = False


class RevealedBank(BaseModel):
    bank_code: str
    branch: str
    account: str


def _audit(session: Session, tenant_id: UUID, action: str, kind: str, entity_id: UUID) -> None:
    session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (:tenant_id, 'user', app.current_user_id(), :action, :kind, :entity_id,
                    CAST('{}' AS jsonb))
        """),
        {"tenant_id": tenant_id, "action": action, "kind": kind, "entity_id": entity_id},
    )


def _employment(session: Session, user_id: UUID, can_reveal: bool) -> Employment:
    row = (
        session.execute(
            text("""
                SELECT employment_type, currency, monthly_amount_minor, hourly_rate_minor,
                       scope_pct, start_date, work_days_per_week, job_title,
                       billing_location_id, pension, study_fund, employment_notice_date,
                       bank_last4
                FROM app.employment_profiles WHERE user_id = :id
            """),
            {"id": user_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return Employment(exists=False)
    return Employment(exists=True, can_reveal_bank=can_reveal, **row)


def _bank_blob(account: BankAccount) -> bytes:
    return secrets.encrypt(account.model_dump())


@router.get("/staff/{user_id}/employment")
def get_employment(user_id: UUID, context: PayrollReadDep) -> Employment:
    _ensure_member_in_reach(context, user_id)
    return _employment(context.session, user_id, Permission.IDENTITY_READ in context.permissions)


@router.put("/staff/{user_id}/employment")
def set_employment(user_id: UUID, body: EmploymentBody, context: PayrollManageDep) -> Employment:
    _ensure_member_in_reach(context, user_id)
    if body.employment_type == "hourly" and not body.hourly_rate_minor:
        raise HTTPException(status_code=422, detail="hourly_rate_required")
    if body.employment_type != "hourly" and body.monthly_amount_minor is None:
        raise HTTPException(status_code=422, detail="monthly_amount_required")
    pension = body.pension.model_dump(mode="json") if body.pension else None
    study_fund = body.study_fund.model_dump(mode="json") if body.study_fund else None
    values: dict[str, Any] = {
        "tenant_id": context.tenant_id,
        "user_id": user_id,
        "employment_type": body.employment_type,
        "currency": body.currency,
        "monthly_amount_minor": body.monthly_amount_minor,
        "hourly_rate_minor": body.hourly_rate_minor,
        "scope_pct": body.scope_pct,
        "start_date": body.start_date,
        "work_days_per_week": body.work_days_per_week,
        "job_title": body.job_title,
        "billing_location_id": body.billing_location_id,
        "pension": json.dumps(pension) if pension else None,
        "study_fund": json.dumps(study_fund) if study_fund else None,
        "notice": body.employment_notice_date,
        "bank_blob": _bank_blob(body.bank) if body.bank else None,
        "bank_last4": body.bank.account[-4:] if body.bank else None,
    }
    if body.billing_location_id is not None:
        found = context.session.execute(
            text("SELECT 1 FROM app.locations WHERE id = :id"), {"id": body.billing_location_id}
        ).first()
        if found is None:
            raise HTTPException(status_code=422, detail="invalid_reference")
    context.session.execute(
        text("""
            INSERT INTO app.employment_profiles
                (tenant_id, user_id, employment_type, currency, monthly_amount_minor,
                 hourly_rate_minor, scope_pct, start_date, work_days_per_week, job_title,
                 billing_location_id, pension, study_fund, employment_notice_date,
                 bank_encrypted, bank_last4)
            VALUES (:tenant_id, :user_id, :employment_type, :currency, :monthly_amount_minor,
                    :hourly_rate_minor, :scope_pct, :start_date, :work_days_per_week, :job_title,
                    :billing_location_id, CAST(:pension AS jsonb), CAST(:study_fund AS jsonb),
                    :notice, :bank_blob, :bank_last4)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                employment_type = excluded.employment_type, currency = excluded.currency,
                monthly_amount_minor = excluded.monthly_amount_minor,
                hourly_rate_minor = excluded.hourly_rate_minor, scope_pct = excluded.scope_pct,
                start_date = excluded.start_date,
                work_days_per_week = excluded.work_days_per_week,
                job_title = excluded.job_title,
                billing_location_id = excluded.billing_location_id,
                pension = excluded.pension, study_fund = excluded.study_fund,
                employment_notice_date = excluded.employment_notice_date,
                bank_encrypted = coalesce(excluded.bank_encrypted,
                                          app.employment_profiles.bank_encrypted),
                bank_last4 = coalesce(excluded.bank_last4, app.employment_profiles.bank_last4),
                updated_at = now()
        """),
        values,
    )
    _audit(context.session, context.tenant_id, "payroll.employment_set", "member", user_id)
    return _employment(context.session, user_id, Permission.IDENTITY_READ in context.permissions)


@router.post("/staff/{user_id}/employment/bank/reveal")
def reveal_bank(user_id: UUID, context: RevealDep) -> RevealedBank:
    _ensure_member_in_reach(context, user_id)
    blob = context.session.execute(
        text("SELECT bank_encrypted FROM app.employment_profiles WHERE user_id = :id"),
        {"id": user_id},
    ).scalar()
    if blob is None:
        raise not_found()
    _audit(context.session, context.tenant_id, "payroll.bank_revealed", "member", user_id)
    return RevealedBank(**secrets.decrypt(blob))


@router.get("/me/employment")
def my_employment(context: TenantDep, user: UserDep) -> Employment:
    """The signed-in team member's own terms (no bank account)."""
    return _employment(context.session, user.id, can_reveal=False)


# Form 101 -------------------------------------------------------------------------------------


class Child(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    birth_year: int = Field(ge=1990, le=2100)
    receives_allowance: bool = False
    lives_with_me: bool = True


class OtherIncome(BaseModel):
    kind: Literal["none", "salary", "other"] = "none"
    tax_coordination: bool = False


class Form101Answers(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    birth_date: date
    gender: Literal["female", "male", "other"]
    address: str = Field(min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=40)
    marital_status: Literal["single", "married", "divorced", "widowed", "separated"]
    spouse_works: bool | None = None
    children: list[Child] = Field(default_factory=list, max_length=20)
    single_parent: bool = False
    resident: bool = True
    new_immigrant_date: date | None = None
    discharged_soldier_date: date | None = None
    academic_degree_year: int | None = Field(default=None, ge=1950, le=2100)
    disability_percent: int = Field(default=0, ge=0, le=100)
    eligible_locality: bool = False
    other_income: OtherIncome = Field(default_factory=OtherIncome)


class Form101Submit(BaseModel):
    answers: Form101Answers
    signed_name: str = Field(min_length=2, max_length=160)

    @field_validator("signed_name", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Form101Request(BaseModel):
    tax_year: int = Field(ge=2000, le=2100)


class CreditOverride(BaseModel):
    points: Decimal | None = Field(
        default=None, ge=0, le=99, description="Replaces the computed points; null clears it"
    )
    note: str | None = Field(default=None, max_length=500)


class Form101Summary(BaseModel):
    tax_year: int
    status: Literal["requested", "submitted"]
    requested_at: datetime
    submitted_at: datetime | None
    signed_name: str | None
    computed_points: Decimal | None
    override_points: Decimal | None
    override_note: str | None
    credit_points: Decimal | None = Field(description="The override when set, else computed")


class Form101Detail(Form101Summary):
    answers: Form101Answers | None


_FORM_SELECT = """
    SELECT tax_year, status, requested_at, submitted_at, signed_name,
           credit_points AS computed_points, credit_points_override AS override_points,
           override_note, answers_encrypted
    FROM app.form101_forms
"""


def _form(row: Any, with_answers: bool) -> Form101Detail:
    data = dict(row)
    blob = data.pop("answers_encrypted")
    answers = None
    if with_answers and blob:
        answers = Form101Answers.model_validate_json(secrets.decrypt(blob)["answers"])
    override = data["override_points"]
    return Form101Detail(
        **data,
        credit_points=override if override is not None else data["computed_points"],
        answers=answers,
    )


def _find_form(session: Session, user_id: UUID, tax_year: int) -> Any:
    return (
        session.execute(
            text(_FORM_SELECT + " WHERE user_id = :id AND tax_year = :year"),
            {"id": user_id, "year": tax_year},
        )
        .mappings()
        .first()
    )


def _list_forms(session: Session, user_id: UUID) -> list[Form101Summary]:
    rows = (
        session.execute(
            text(_FORM_SELECT + " WHERE user_id = :id ORDER BY tax_year DESC"),
            {"id": user_id},
        )
        .mappings()
        .all()
    )
    return [Form101Summary(**_form(row, False).model_dump(exclude={"answers"})) for row in rows]


@router.get("/staff/{user_id}/form101")
def member_forms(user_id: UUID, context: PayrollReadDep) -> list[Form101Summary]:
    _ensure_member_in_reach(context, user_id)
    return _list_forms(context.session, user_id)


@router.post("/staff/{user_id}/form101", status_code=status.HTTP_201_CREATED)
def request_form(user_id: UUID, body: Form101Request, context: PayrollManageDep) -> Form101Summary:
    _ensure_member_in_reach(context, user_id)
    if _find_form(context.session, user_id, body.tax_year) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="form_exists")
    context.session.execute(
        text("""
            INSERT INTO app.form101_forms (tenant_id, user_id, tax_year, requested_by)
            VALUES (:tenant_id, :user_id, :year, app.current_user_id())
        """),
        {"tenant_id": context.tenant_id, "user_id": user_id, "year": body.tax_year},
    )
    _audit(context.session, context.tenant_id, "payroll.form101_requested", "member", user_id)
    row = _find_form(context.session, user_id, body.tax_year)
    return Form101Summary(**_form(row, False).model_dump(exclude={"answers"}))


@router.get("/staff/{user_id}/form101/{tax_year}")
def member_form(user_id: UUID, tax_year: int, context: PayrollReadDep) -> Form101Detail:
    _ensure_member_in_reach(context, user_id)
    row = _find_form(context.session, user_id, tax_year)
    if row is None:
        raise not_found()
    _audit(context.session, context.tenant_id, "payroll.form101_viewed", "member", user_id)
    return _form(row, True)


@router.put("/staff/{user_id}/form101/{tax_year}/credit-points")
def override_points(
    user_id: UUID, tax_year: int, body: CreditOverride, context: PayrollManageDep
) -> Form101Summary:
    _ensure_member_in_reach(context, user_id)
    updated = context.session.execute(
        text("""
            UPDATE app.form101_forms
            SET credit_points_override = :points, override_note = :note, updated_at = now()
            WHERE user_id = :id AND tax_year = :year AND status = 'submitted'
        """),
        {
            "points": body.points,
            "note": body.note if body.points is not None else None,
            "id": user_id,
            "year": tax_year,
        },
    ).rowcount
    if not updated:
        raise not_found()
    _audit(context.session, context.tenant_id, "payroll.credit_points_set", "member", user_id)
    row = _find_form(context.session, user_id, tax_year)
    return Form101Summary(**_form(row, False).model_dump(exclude={"answers"}))


@router.get("/me/form101")
def my_forms(context: TenantDep, user: UserDep) -> list[Form101Summary]:
    return _list_forms(context.session, user.id)


@router.get("/me/form101/{tax_year}")
def my_form(tax_year: int, context: TenantDep, user: UserDep) -> Form101Detail:
    row = _find_form(context.session, user.id, tax_year)
    if row is None:
        raise not_found()
    return _form(row, True)


@router.put("/me/form101/{tax_year}")
def submit_form(
    tax_year: int, body: Form101Submit, context: TenantDep, user: UserDep
) -> Form101Detail:
    """The employee fills in and signs (by typing their name) the form for the year. A form
    nobody requested can also be started by the employee. Signing again replaces the answers."""
    if not 2000 <= tax_year <= 2100:
        raise not_found()
    answers = body.answers.model_dump(mode="json")
    points = credit_points.compute(answers, tax_year)
    blob = secrets.encrypt({"answers": body.answers.model_dump_json()})
    context.session.execute(
        text("""
            INSERT INTO app.form101_forms
                (tenant_id, user_id, tax_year, status, answers_encrypted, credit_points,
                 submitted_at, signed_name)
            VALUES (:tenant_id, :user_id, :year, 'submitted', :blob, :points, now(), :name)
            ON CONFLICT (tenant_id, user_id, tax_year) DO UPDATE SET
                status = 'submitted', answers_encrypted = excluded.answers_encrypted,
                credit_points = excluded.credit_points, submitted_at = now(),
                signed_name = excluded.signed_name, credit_points_override = NULL,
                override_note = NULL, updated_at = now()
        """),
        {
            "tenant_id": context.tenant_id,
            "user_id": user.id,
            "year": tax_year,
            "blob": blob,
            "points": points,
            "name": body.signed_name,
        },
    )
    _audit(context.session, context.tenant_id, "payroll.form101_signed", "member", user.id)
    keep_copy(
        context.session,
        context.tenant_id,
        "employees",
        name=f"form-101-{tax_year}-{safe_name(body.signed_name)}.pdf",
        content=form_pdf(context.session, user.id, tax_year),
        owner_user_id=user.id,
    )
    return _form(_find_form(context.session, user.id, tax_year), True)


# The signed form as a PDF ---------------------------------------------------------------------

PDF_RESPONSES: dict[int | str, dict[str, Any]] = {200: {"content": {"application/pdf": {}}}}


def form_pdf(session: Session, user_id: UUID, tax_year: int) -> bytes:
    from app.api.pdf import _tenant
    from app.documents import render

    row = _find_form(session, user_id, tax_year)
    if row is None or row["status"] != "submitted":
        raise not_found()
    form = _form(row, True)
    assert form.answers is not None
    tenant = _tenant(session)
    lang = render.language(tenant["locale"])
    t = render.texts(lang)
    answers = form.answers
    id_last4 = session.execute(
        text("SELECT id_last4 FROM app.person_identities WHERE user_id = :id"), {"id": user_id}
    ).scalar()
    logo = (
        render.data_uri(bytes(tenant["logo"]), tenant["logo_content_type"])
        if tenant["logo"] and tenant["logo_content_type"]
        else None
    )
    assert form.submitted_at is not None
    return render.render_pdf(
        "form101",
        lang,
        {
            "accent": render.accent(tenant["primary_color"]),
            "issuer": {"name": tenant["name"], "logo": logo, "lines": []},
            "doc_title": render.fill(t["form101"], year=tax_year),
            "doc_number": "",
            "sample_note": None,
            "watermark": None,
            "footer_right": "",
            "answers": answers,
            "id_last4": id_last4,
            "points": form.credit_points,
            "override_note": form.override_note,
            "signed_name": form.signed_name,
            "signed_on": render.day(form.submitted_at, lang, tenant["time_zone"]),
            "birth": render.day(answers.birth_date, lang),
        },
    )


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


@router.get(
    "/staff/{user_id}/form101/{tax_year}/pdf", response_class=Response, responses=PDF_RESPONSES
)
def member_form_file(user_id: UUID, tax_year: int, context: PayrollReadDep) -> Response:
    _ensure_member_in_reach(context, user_id)
    _audit(context.session, context.tenant_id, "payroll.form101_viewed", "member", user_id)
    return _pdf(form_pdf(context.session, user_id, tax_year), f"form-101-{tax_year}")


@router.get("/me/form101/{tax_year}/pdf", response_class=Response, responses=PDF_RESPONSES)
def my_form_file(tax_year: int, context: TenantDep, user: UserDep) -> Response:
    return _pdf(form_pdf(context.session, user.id, tax_year), f"form-101-{tax_year}")
