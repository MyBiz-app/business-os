"""Ending or pausing the business's MyBiz subscription (round 7, R33).

The policy (also on the landing site, /legal/cancellation): cancel any time with no penalty, the
account works until the end of the paid month and nothing is billed after; cancelling within 14
days of the first payment refunds it in full. A pause keeps the data and the account read-only for
up to three months at a flat fee. No card is charged or refunded while payments are off, so a
refund is only recorded here. Owners only."""

from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.billing import Collection, _collection, _invoices
from app.api.closure import OwnerDep
from app.commerce.billing import MAX_PAUSE_MONTHS, PAUSE_FEE, add_months
from app.core.audit import record
from app.core.logging import log
from app.messaging.email import Email, load_all_messages, sender_from_settings

router = APIRouter(prefix="/billing", tags=["billing"])

Reason = Literal["too_expensive", "missing_feature", "not_using", "switched", "other"]
REFUND_WINDOW_DAYS = 14


class CancelRequest(BaseModel):
    reason: Reason | None = Field(default=None, description="Why, from a short list (optional)")
    note: str | None = Field(default=None, max_length=1000)


class PauseRequest(BaseModel):
    months: int = Field(ge=1, le=MAX_PAUSE_MONTHS)
    reason: Reason | None = None


class CancelOptions(BaseModel):
    """What cancelling would do now, and what a pause costs, shown before the owner decides."""

    ends_at: datetime = Field(description="When the subscription would end")
    currency: str
    refund_minor: int | None = Field(description="The first payment, refunded inside 14 days")
    pause_fee_minor: int = Field(description="Per month while paused, minor units")
    pause_max_months: int
    pause_available: bool = Field(description="False in the trial, when cancelling or overdue")


def _tenant(db: Session):
    return db.execute(
        text("""
            SELECT name, locale, time_zone, currency, trial_ends_at, billing_state, cancel_at,
                   pause_from, pause_until
            FROM app.tenants WHERE id = app.current_tenant_id()
        """)
    ).one()


def _period_end(tenant) -> datetime:
    """When the paid period that contains today ends (the trial's end while in the trial)."""
    zone = ZoneInfo(tenant.time_zone)
    now = datetime.now(UTC)
    if tenant.trial_ends_at > now:
        return tenant.trial_ends_at
    anchor = tenant.trial_ends_at.astimezone(zone).date()
    today = now.astimezone(zone).date()
    months = 0
    while add_months(anchor, months + 1) <= today:
        months += 1
    return datetime.combine(add_months(anchor, months + 1), datetime.min.time(), tzinfo=zone)


def _first_payment_refund(db: Session) -> tuple[object | None, int]:
    """The first paid invoice and what it refunds: all of it inside 14 days, once."""
    invoice = db.execute(
        text("""
            SELECT i.id, i.total, i.paid_at FROM app.platform_invoices i
            WHERE i.status = 'paid' ORDER BY i.period_start LIMIT 1
        """)
    ).first()
    if invoice is None or invoice.paid_at is None:
        return None, 0
    if (datetime.now(UTC) - invoice.paid_at).days >= REFUND_WINDOW_DAYS:
        return None, 0
    taken = db.execute(
        text("SELECT 1 FROM app.subscription_cancellations WHERE refund_invoice_id = :id"),
        {"id": invoice.id},
    ).first()
    return (None, 0) if taken else (invoice.id, invoice.total)


def _record(
    db: Session,
    outcome: str,
    reason: str | None,
    note: str | None,
    ends_at: datetime,
    currency: str,
    refund_invoice_id: object | None = None,
    refund_minor: int = 0,
) -> None:
    db.execute(
        text("""
            INSERT INTO app.subscription_cancellations
                (tenant_id, user_id, outcome, reason, note, ends_at, refund_invoice_id,
                 refund_minor, currency)
            VALUES (app.current_tenant_id(), app.current_user_id(), :outcome, :reason, :note,
                    :ends_at, :invoice, :refund, :currency)
        """),
        {
            "outcome": outcome,
            "reason": reason,
            "note": (note or "").strip() or None,
            "ends_at": ends_at,
            "invoice": refund_invoice_id,
            "refund": refund_minor,
            "currency": currency,
        },
    )


def _confirm(db: Session, tenant, kind: str, ends_at: datetime, refund_minor: int = 0) -> None:
    """Emails the owner the date the subscription ends (or the pause ends)."""
    sender = sender_from_settings()
    if sender is None:
        return
    to = db.execute(text("SELECT email FROM app.users WHERE id = app.current_user_id()")).scalar()
    if not to:
        return
    locale = tenant.locale if tenant.locale in ("he", "en") else "en"
    messages = load_all_messages(locale)["cancellationEmail"]
    date = ends_at.astimezone(ZoneInfo(tenant.time_zone)).strftime("%d/%m/%Y")
    refund = f"{refund_minor / 100:,.2f} {tenant.currency}"
    values = {"business": tenant.name, "date": date, "refund": refund}

    def fill(template: str) -> str:
        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    body = [messages["greeting"], "", fill(messages["body"][kind])]
    if kind == "cancelled" and refund_minor:
        body += ["", fill(messages["refund"])]
    body += ["", messages["footer"]]
    try:
        sender.send(
            Email(
                to=to,
                subject=fill(messages["subject"][kind]),
                text="\n".join(body),
                locale=locale,
                details=((messages["details"]["date"], date),),
                kind="billing",
            )
        )
    except Exception as error:  # the confirmation is also on screen; a mail failure is not ours
        log(40, "subscription email failed", error=type(error).__name__)


@router.get("/cancel")
def cancel_options(context: OwnerDep) -> CancelOptions:
    db = context.session
    tenant = _tenant(db)
    _, refund = _first_payment_refund(db)
    return CancelOptions(
        ends_at=_period_end(tenant),
        currency=tenant.currency,
        refund_minor=refund or None,
        pause_fee_minor=PAUSE_FEE.get(tenant.currency, PAUSE_FEE["USD"]),
        pause_max_months=MAX_PAUSE_MONTHS,
        pause_available=_pause_blocker(tenant) is None,
    )


def _pause_blocker(tenant) -> str | None:
    now = datetime.now(UTC)
    if tenant.trial_ends_at > now:
        return "in_trial"
    if tenant.cancel_at is not None:
        return "cancelling"
    if tenant.billing_state != "active":
        return "payment_overdue"
    if tenant.pause_until is not None and tenant.pause_until > now:
        return "already_paused"
    return None


@router.post("/cancel")
def cancel_subscription(context: OwnerDep, body: CancelRequest | None = None) -> Collection:
    """Ends the subscription at the end of the paid period (or the trial). The business and its
    data are kept; nothing is billed after that, and the owner can resume until it ends or later.
    The first payment is refunded (recorded) when this is inside 14 days of it."""
    db = context.session
    tenant = _tenant(db)
    if tenant.cancel_at is not None and tenant.cancel_at > datetime.now(UTC):
        return _collection(db, _invoices(db), tenant.time_zone)  # already set; nothing to redo
    end = _period_end(tenant)
    invoice_id, refund = _first_payment_refund(db)
    db.execute(text("SELECT app.set_subscription_cancel(:at)"), {"at": end})
    body = body or CancelRequest()
    _record(db, "cancelled", body.reason, body.note, end, tenant.currency, invoice_id, refund)
    record(db, "tenant.subscription_canceled", entity_type="tenant", ends_at=end)
    _confirm(db, tenant, "cancelled", end, refund)
    return _collection(db, _invoices(db), tenant.time_zone)


@router.delete("/cancel")
def resume_subscription(context: OwnerDep) -> Collection:
    """Takes a cancellation back, and brings a business back whose subscription had ended."""
    db = context.session
    db.execute(text("SELECT app.set_subscription_cancel(NULL)"))
    record(db, "tenant.subscription_resumed", entity_type="tenant")
    db.execute(
        text("""
            UPDATE app.subscription_cancellations SET resumed_at = now()
            WHERE tenant_id = app.current_tenant_id() AND outcome = 'cancelled'
              AND resumed_at IS NULL
        """)
    )
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return _collection(db, _invoices(db), time_zone)


@router.post("/pause")
def pause_subscription(body: PauseRequest, context: OwnerDep) -> Collection:
    """Pauses the account for 1 to 3 months: the data is kept, everything is read-only and the
    flat pause fee replaces the modules' price. Billing goes back to normal after it."""
    db = context.session
    tenant = _tenant(db)
    blocker = _pause_blocker(tenant)
    if blocker is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocker)
    zone = ZoneInfo(tenant.time_zone)
    now = datetime.now(UTC)
    until = datetime.combine(
        add_months(now.astimezone(zone).date(), body.months), datetime.min.time(), tzinfo=zone
    )
    db.execute(text("SELECT app.subscription_pause(now(), :until)"), {"until": until})
    _record(db, "paused", body.reason, None, until, tenant.currency)
    _confirm(db, tenant, "paused", until)
    return _collection(db, _invoices(db), tenant.time_zone)


@router.delete("/pause")
def end_pause(context: OwnerDep) -> Collection:
    """Ends a pause now; billing is normal again from the next period."""
    db = context.session
    db.execute(text("SELECT app.subscription_pause(NULL, NULL)"))
    db.execute(
        text("""
            UPDATE app.subscription_cancellations SET resumed_at = now()
            WHERE tenant_id = app.current_tenant_id() AND outcome = 'paused'
              AND resumed_at IS NULL
        """)
    )
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return _collection(db, _invoices(db), time_zone)
