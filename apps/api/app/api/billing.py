"""The business's MyBiz subscription (simulated, see app/billing.py): trial, plan, test card,
billing details and invoices. Owners and anyone with `business.settings`."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found
from app.api.deps import TenantContext, require
from app.api.modules import QuoteOut, _tenant_modules
from app.billing import add_months
from app.permissions import Permission

router = APIRouter(prefix="/billing", tags=["billing"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

CardBrand = Literal["visa", "mastercard", "amex"]
# Test cards only: the prototype never collects real card numbers.
TEST_CARDS: dict[str, str] = {"visa": "4242", "mastercard": "4444", "amex": "0005"}


class PaymentMethod(BaseModel):
    brand: CardBrand
    last4: str
    exp: str = Field(description="MM/YY")
    simulated: bool


class BillingDetails(BaseModel):
    billing_name: str | None = Field(default=None, max_length=160)
    billing_email: EmailStr | None = None
    tax_id: str | None = Field(default=None, max_length=40)

    @field_validator("billing_name", "billing_email", "tax_id", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class InvoiceLine(BaseModel):
    key: str = Field(description='"core" or a module key')
    quantity: int
    amount: int


class InvoiceSummary(BaseModel):
    id: UUID
    number: int
    period_start: date
    period_end: date
    currency: str
    total: int
    status: Literal["open", "paid", "void"]
    issued_at: datetime
    paid_at: datetime | None


class Invoice(InvoiceSummary):
    business_name: str
    billing: BillingDetails
    active_clients: int
    lines: list[InvoiceLine]
    card_last4: str | None
    simulated: bool


class Billing(BaseModel):
    trial_ends_at: datetime
    in_trial: bool
    trial_days_left: int
    next_invoice_on: date = Field(description="When the current period ends and is invoiced")
    estimate: QuoteOut = Field(description="The current monthly price (modules and clients now)")
    payment_method: PaymentMethod | None
    details: BillingDetails
    invoices: list[InvoiceSummary]
    balance_due: int = Field(description="Sum of open invoices, minor units")


class TestCardRequest(BaseModel):
    brand: CardBrand = "visa"


def _account(db: Session) -> dict | None:
    row = (
        db.execute(
            text("SELECT * FROM app.billing_accounts WHERE tenant_id = app.current_tenant_id()")
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _details(account: dict | None) -> BillingDetails:
    if account is None:
        return BillingDetails()
    return BillingDetails.model_validate(
        {k: account[k] for k in ("billing_name", "billing_email", "tax_id")}
    )


def _method(account: dict | None) -> PaymentMethod | None:
    if account is None or account["card_last4"] is None:
        return None
    return PaymentMethod(
        brand=account["card_brand"],
        last4=account["card_last4"],
        exp=account["card_exp"],
        simulated=account["card_simulated"],
    )


INVOICE_COLUMNS = (
    "id, number, period_start, period_end, currency, total, status, issued_at, paid_at"
)


@router.get("")
def get_billing(context: SettingsDep) -> Billing:
    db = context.session
    tenant = db.execute(
        text("SELECT trial_ends_at, time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).one()
    now = datetime.now(UTC)
    zone = ZoneInfo(tenant.time_zone)
    anchor = tenant.trial_ends_at.astimezone(zone).date()
    today = now.astimezone(zone).date()
    # The period that contains today (the first one while in trial) ends on the next invoice day.
    months = 0
    while add_months(anchor, months + 1) <= today:
        months += 1
    next_invoice_on = add_months(anchor, months + 1) - timedelta(days=1)
    rows = db.execute(
        text(f"SELECT {INVOICE_COLUMNS} FROM app.platform_invoices ORDER BY period_start DESC")
    ).mappings()
    invoices = [InvoiceSummary.model_validate(dict(r)) for r in rows]
    account = _account(db)
    seconds_left = (tenant.trial_ends_at - now).total_seconds()
    return Billing(
        trial_ends_at=tenant.trial_ends_at,
        in_trial=seconds_left > 0,
        trial_days_left=max(0, -(-int(seconds_left) // 86400)),
        next_invoice_on=next_invoice_on,
        estimate=_tenant_modules(db).quote,
        payment_method=_method(account),
        details=_details(account),
        invoices=invoices,
        balance_due=sum(i.total for i in invoices if i.status == "open"),
    )


def _upsert(db: Session, tenant_id: UUID, values: dict) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join(f":{k}" for k in values)
    updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in values)
    db.execute(
        text(f"""
            INSERT INTO app.billing_accounts (tenant_id, {columns})
            VALUES (:tenant_id, {placeholders})
            ON CONFLICT (tenant_id) DO UPDATE SET {updates}, updated_at = now()
        """),
        {"tenant_id": tenant_id, **values},
    )


@router.put("/details")
def set_details(body: BillingDetails, context: SettingsDep) -> BillingDetails:
    _upsert(context.session, context.tenant_id, body.model_dump())
    return _details(_account(context.session))


@router.post("/payment-method")
def add_test_card(body: TestCardRequest, context: SettingsDep) -> PaymentMethod:
    """Adds a test card (no card number is ever entered in the prototype)."""
    exp = add_months(datetime.now(UTC).date(), 36)
    _upsert(
        context.session,
        context.tenant_id,
        {
            "card_brand": body.brand,
            "card_last4": TEST_CARDS[body.brand],
            "card_exp": f"{exp.month:02d}/{exp.year % 100:02d}",
            "card_simulated": True,
        },
    )
    method = _method(_account(context.session))
    assert method is not None
    return method


@router.delete("/payment-method", status_code=status.HTTP_204_NO_CONTENT)
def remove_card(context: SettingsDep) -> None:
    context.session.execute(
        text("""
            UPDATE app.billing_accounts
            SET card_brand = NULL, card_last4 = NULL, card_exp = NULL, updated_at = now()
            WHERE tenant_id = app.current_tenant_id()
        """)
    )


def _invoice(db: Session, invoice_id: UUID) -> Invoice:
    row = (
        db.execute(
            text(f"""
                SELECT {INVOICE_COLUMNS}, active_clients, lines, card_last4, simulated,
                       (SELECT name FROM app.tenants WHERE id = tenant_id) AS business_name
                FROM app.platform_invoices WHERE id = :id
            """),
            {"id": invoice_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Invoice(**dict(row), billing=_details(_account(db)))


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: UUID, context: SettingsDep) -> Invoice:
    return _invoice(context.session, invoice_id)


@router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: UUID, context: SettingsDep) -> Invoice:
    """Charges an open invoice to the business's (test) card."""
    db = context.session
    try:
        with db.begin_nested():
            db.execute(text("SELECT app.pay_platform_invoice(:id)"), {"id": invoice_id})
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0001":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="no_payment_method"
            ) from error
        if code == "P0002":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_open") from error
        raise
    return _invoice(db, invoice_id)
