"""Clients buying plans in the client app (checkouts). The business's payments provider takes
the payment on its own hosted page and tells us by a webhook (app/api/webhooks.py); with the
built-in simulated provider the app's "pay" button completes it. The business turns online
sales on in its settings."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.common import not_found
from app.api.deps import ClientDep
from app.api.plans import Entitlement, issue_receipts_now, load_entitlement
from app.commerce.payments import provider_for_business
from app.core.config import get_settings
from app.providers.choice import choose
from app.providers.payments import CheckoutRequest, PaymentsUnavailable

router = APIRouter(prefix="/client", tags=["client"])


class CheckoutCreate(BaseModel):
    plan_id: UUID


class Checkout(BaseModel):
    id: UUID
    plan_id: UUID
    plan_name: str
    amount: int = Field(description="What the client pays, minor units")
    list_amount: int = Field(description="The plan's price before a promo code")
    discount: int
    promo_code: str | None
    currency: str
    status: Literal["pending", "paid", "cancelled", "failed"]
    simulated: bool = Field(description="Test payment: no money is charged")
    pay_url: str | None = Field(description="Where to pay (real providers only)")
    created_at: datetime


class CheckoutPaid(BaseModel):
    checkout: Checkout
    entitlement: Entitlement


SELECT = """
    SELECT k.id, k.plan_id, p.name AS plan_name, k.amount, k.list_amount, k.discount,
           (SELECT c.code FROM app.promo_codes c WHERE c.id = k.promo_code_id) AS promo_code,
           k.currency, k.status, k.provider = 'simulated' AS simulated, k.pay_url,
           k.created_at
    FROM app.checkouts k JOIN app.plans p ON p.id = k.plan_id
"""


def _load(context: ClientDep, checkout_id: UUID) -> Checkout:
    row = (
        context.session.execute(text(f"{SELECT} WHERE k.id = :id"), {"id": checkout_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Checkout.model_validate(dict(row))


@router.post("/checkouts", status_code=status.HTTP_201_CREATED)
def start_checkout(body: CheckoutCreate, context: ClientDep) -> Checkout:
    """Starts buying a plan at its current price."""
    db = context.session
    online = db.execute(
        text("SELECT online_sales FROM app.tenants WHERE id = :id"), {"id": context.tenant_id}
    ).scalar_one()
    if not online:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="online_sales_off")
    checkout_id = db.execute(
        text("""
            INSERT INTO app.checkouts
                (tenant_id, client_id, plan_id, amount, currency, provider)
            SELECT :tenant_id, :client_id, p.id, p.price_amount, p.price_currency, :provider
            FROM app.plans p WHERE p.id = :plan_id AND p.active
            RETURNING id
        """),
        {
            "tenant_id": context.tenant_id,
            "client_id": context.client_id,
            "plan_id": body.plan_id,
            "provider": provider_for_business(db, context.tenant_id),
        },
    ).scalar()
    if checkout_id is None:
        raise not_found()
    return _load(context, checkout_id)


@router.get("/checkouts/{checkout_id}")
def get_checkout(checkout_id: UUID, context: ClientDep) -> Checkout:
    return _load(context, checkout_id)


class PromoCodeApply(BaseModel):
    code: str | None = Field(default=None, max_length=20, description="Empty removes the code")


@router.post("/checkouts/{checkout_id}/promo")
def apply_promo(checkout_id: UUID, body: PromoCodeApply, context: ClientDep) -> Checkout:
    """Applies (or removes) a promo code on the client's pending checkout."""
    db = context.session
    try:
        with db.begin_nested():
            db.execute(
                text("SELECT app.apply_promo_code(:id, :code)"),
                {"id": checkout_id, "code": body.code},
            )
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise not_found() from error
        if code == "22023":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_code"
            ) from error
        if code == "P0001":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="not_pending"
            ) from error
        raise
    return _load(context, checkout_id)


@router.post("/checkouts/{checkout_id}/pay-page")
def pay_page(checkout_id: UUID, context: ClientDep) -> Checkout:
    """The provider's hosted payment page for the checkout at its current amount (after any
    promo code). The client pays there; the provider's webhook completes the checkout."""
    checkout = _load(context, checkout_id)
    if checkout.simulated or checkout.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no_pay_page")
    db = context.session
    client = (
        db.execute(
            text("""
                SELECT trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS name, c.email,
                       t.locale
                FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id WHERE c.id = :id
            """),
            {"id": context.client_id},
        )
        .mappings()
        .one()
    )
    app_url = get_settings().client_app_url
    try:
        hosted = choose(db, context.tenant_id, "payments").instance.create_checkout(
            CheckoutRequest(
                checkout_id=str(checkout.id),
                amount=checkout.amount,
                currency=checkout.currency,
                description=checkout.plan_name,
                client_name=client["name"],
                client_email=client["email"],
                success_url=f"{app_url}/pay/{checkout.id}?done=1",
                cancel_url=f"{app_url}/pay/{checkout.id}",
                locale=client["locale"],
            )
        )
    except PaymentsUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="payments_unavailable"
        ) from error
    db.execute(
        text("UPDATE app.checkouts SET pay_url = :url, provider_ref = :ref WHERE id = :id"),
        {"url": hosted.pay_url, "ref": hosted.provider_ref, "id": checkout_id},
    )
    return _load(context, checkout_id)


@router.post("/checkouts/{checkout_id}/simulate-payment")
def simulate_payment(checkout_id: UUID, context: ClientDep) -> CheckoutPaid:
    """Completes a simulated checkout: records a test payment and creates the plan. Calling it
    again returns the same plan."""
    checkout = _load(context, checkout_id)
    if not checkout.simulated:
        raise not_found()
    db = context.session
    try:
        with db.begin_nested():
            entitlement_id = db.execute(
                text("SELECT app.complete_checkout(:id)"), {"id": checkout_id}
            ).scalar_one()
            issue_receipts_now(db)
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "P0002":
            raise not_found() from error
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="checkout_closed"
        ) from error
    return CheckoutPaid(
        checkout=_load(context, checkout_id), entitlement=load_entitlement(db, entitlement_id)
    )
