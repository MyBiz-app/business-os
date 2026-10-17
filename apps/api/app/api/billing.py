"""The business's MyBiz subscription (simulated, see app/commerce/billing.py): trial, plan,
test card, billing details and invoices. Owners and anyone with `business.settings`."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.ai import budget as ai_budget
from app.api.closure import OwnerDep
from app.api.common import blank_to_none, check_columns, not_found
from app.api.deps import TenantContext, require
from app.api.modules import QuoteOut, _tenant_modules, enabled_modules
from app.commerce.billing import add_months
from app.commerce.modules import allowance
from app.core.config import get_settings
from app.core.permissions import Permission

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
    subtotal: int = Field(description="Before VAT, minor units")
    vat_rate_bp: int = Field(description="VAT rate in basis points (1800 = 18%); 0 for no VAT")
    vat_amount: int
    total: int = Field(description="Including VAT")
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


class Usage(BaseModel):
    """This calendar month's use against the business's bundle (space and messages)."""

    pack: Literal["pack_plus", "pack_max"] | None = Field(description="None: the included one")
    month_start: date
    messages: int = Field(description="Messages sent this month (all channels)")
    messages_included: int
    storage_bytes: int = Field(description="Files kept now")
    storage_included_bytes: int
    ai_credits: float = Field(description="AI credits used this month (1 credit = 1 US cent)")
    ai_credits_included: int = Field(description="0 when the business has no AI module")
    ai_extra_minor: int = Field(
        default=0, description="Pay-as-you-go: this month's extra AI use, minor units"
    )


class Collection(BaseModel):
    """Where the subscription stands when an invoice is unpaid or the subscription is ending."""

    state: Literal["active", "read_only", "suspended"] = Field(
        description="read_only: everything visible, nothing can be changed; suspended: no access"
    )
    overdue_since: datetime | None = Field(description="When the oldest unpaid invoice was issued")
    read_only_on: date | None = Field(description="Null when nothing is overdue or dunning is off")
    suspend_on: date | None
    grace_until: datetime | None = Field(description="A grace extension from MyBiz, if any")
    cancel_at: datetime | None = Field(description="The subscription ends then; the business stays")


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
    collection: Collection
    usage: Usage


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
    "id, number, period_start, period_end, currency, coalesce(subtotal, total) AS subtotal, "
    "vat_rate_bp, vat_amount, total, status, issued_at, paid_at"
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
    invoices = _invoices(db)
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
        collection=_collection(db, invoices, tenant.time_zone),
        usage=usage(db, today),
    )


def _collection(db: Session, invoices: list[InvoiceSummary], time_zone: str) -> Collection:
    tenant = db.execute(
        text("""
            SELECT CASE WHEN cancel_at <= now() THEN 'suspended' ELSE billing_state END AS state,
                   billing_grace_until, cancel_at
            FROM app.tenants WHERE id = app.current_tenant_id()
        """)
    ).one()
    policy = db.execute(text("SELECT * FROM app.dunning_settings")).mappings().one()
    open_since = min((i.issued_at for i in invoices if i.status == "open"), default=None)
    zone = ZoneInfo(time_zone)

    def on(days: int) -> date | None:
        if open_since is None or not policy["enabled"]:
            return None
        return (open_since.astimezone(zone) + timedelta(days=days)).date()

    return Collection(
        state=tenant.state,
        overdue_since=open_since,
        read_only_on=on(policy["read_only_after_days"]),
        suspend_on=on(policy["suspend_after_days"]),
        grace_until=tenant.billing_grace_until,
        cancel_at=tenant.cancel_at,
    )


@router.post("/cancel")
def cancel_subscription(context: OwnerDep) -> Collection:
    """Ends the subscription at the end of the paid period (or the trial). The business and its
    data are kept; nothing is billed after that, and the owner can resume until it ends or later."""
    db = context.session
    tenant = db.execute(
        text("SELECT trial_ends_at, time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).one()
    zone = ZoneInfo(tenant.time_zone)
    now = datetime.now(UTC)
    anchor = tenant.trial_ends_at.astimezone(zone).date()
    today = now.astimezone(zone).date()
    if tenant.trial_ends_at > now:
        end = tenant.trial_ends_at
    else:
        months = 0
        while add_months(anchor, months + 1) <= today:
            months += 1
        # The period that contains today is already running; it ends at the start of the next.
        end = datetime.combine(add_months(anchor, months + 1), datetime.min.time(), tzinfo=zone)
    db.execute(text("SELECT app.set_subscription_cancel(:at)"), {"at": end})
    return _collection(db, _invoices(db), tenant.time_zone)


@router.delete("/cancel")
def resume_subscription(context: OwnerDep) -> Collection:
    """Takes a cancellation back, and brings a business back whose subscription had ended."""
    db = context.session
    db.execute(text("SELECT app.set_subscription_cancel(NULL)"))
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return _collection(db, _invoices(db), time_zone)


def _invoices(db: Session) -> list[InvoiceSummary]:
    rows = db.execute(
        text(f"SELECT {INVOICE_COLUMNS} FROM app.platform_invoices ORDER BY period_start DESC")
    ).mappings()
    return [InvoiceSummary.model_validate(dict(r)) for r in rows]


@router.get("/usage")
def get_usage(context: SettingsDep) -> Usage:
    """This month's space and messages, for the warnings on the dashboard and in the app."""
    db = context.session
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return usage(db, datetime.now(ZoneInfo(time_zone)).date())


def usage(db: Session, today: date) -> Usage:
    """Messages counted from usage events since the 1st of the business's month, and the
    files the business keeps now."""
    pack, allowed = allowance(enabled_modules(db))
    month_start = today.replace(day=1)
    row = db.execute(
        text("""
            SELECT
                (SELECT coalesce(sum(u.quantity), 0) FROM app.usage_events u
                 WHERE u.meter = 'messages'
                   AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone))
                    AS messages,
                app.storage_used() AS storage
            FROM app.tenants t WHERE t.id = app.current_tenant_id()
        """),
        {"start": month_start},
    ).one()
    return Usage(
        pack=pack,  # type: ignore[arg-type]
        month_start=month_start,
        messages=int(row.messages),
        messages_included=allowed.messages,
        storage_bytes=int(row.storage),
        storage_included_bytes=allowed.storage_bytes,
        ai_credits=round(ai_budget.credits_used(db, month_start), 2),
        ai_credits_included=ai_budget.credits_included(db),
        ai_extra_minor=_ai_extra(db, month_start),
    )


def _ai_extra(db: Session, month_start: date) -> int:
    spend = ai_budget.spend_settings(db)
    if not spend.payg_enabled:
        return 0
    return spend.extra_minor(
        ai_budget.credits_used(db, month_start), ai_budget.credits_included(db)
    )


# Columns _upsert may write: the billing details form plus the test card fields.
_ACCOUNT_COLUMNS = frozenset(
    {*BillingDetails.model_fields, "card_brand", "card_last4", "card_exp", "card_simulated"}
)


def _upsert(db: Session, tenant_id: UUID, values: dict) -> None:
    check_columns(values, _ACCOUNT_COLUMNS)
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
    # A fake card must never stand in for real billing in production.
    if get_settings().environment == "production":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="test_cards_disabled")
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
