"""SaaS numbers and email deliverability in the MyBiz console (K3).

Both are read-only and built from what the console already reads: the billed invoices, the churn
months and the AI cost board. Billing numbers need `billing.manage`; deliverability needs
`usage.read`. Money is minor units per currency; nothing is converted between currencies."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.platform import AdminDep, BillingDep, UsageDep, billing_summary, churn
from app.api.platform_ai import ai_costs
from app.core.config import get_settings

router = APIRouter(prefix="/platform/metrics", tags=["platform"])


class RevenueMonth(BaseModel):
    month: dt.date
    billed: int = Field(description="Paid and open invoices, minor units")
    paid: int = Field(description="Minor units")
    open: int = Field(description="Minor units")
    invoices: int


class CurrencyMetrics(BaseModel):
    currency: str
    mrr: int = Field(description="Billed in the latest invoiced month, minor units")
    arr: int = Field(description="MRR times twelve, minor units")
    arpu: int = Field(description="MRR per invoiced business, minor units")
    mrr_month: dt.date
    months: list[RevenueMonth]


class ChurnMetrics(BaseModel):
    month: dt.date
    cancelled: int
    paying_at_start: int
    rate: float | None = Field(description="Cancelled over paying at the month's start")


class AIMargin(BaseModel):
    days: int
    cost_usd_minor: int = Field(description="Model cost of the period, US cents")
    revenue_usd_minor: int = Field(description="Monthly price of the AI modules in USD, cents")
    margin_usd_minor: int = Field(description="Revenue minus cost for businesses billed in USD")


class SaasMetrics(BaseModel):
    currencies: list[CurrencyMetrics]
    churn: ChurnMetrics | None
    ai: AIMargin | None = Field(description="Only for team members who may read usage")


@router.get("/saas")
def saas_metrics(db: BillingDep) -> SaasMetrics:
    """MRR, ARR, ARPU, churn and the AI margin, with a month-by-month history."""
    by_currency: dict[str, list[RevenueMonth]] = {}
    for row in sorted(billing_summary(db), key=lambda r: r.month):
        by_currency.setdefault(row.currency, []).append(
            RevenueMonth(
                month=row.month,
                billed=row.paid + row.open,
                paid=row.paid,
                open=row.open,
                invoices=row.invoices,
            )
        )
    currencies: list[CurrencyMetrics] = []
    for currency, months in sorted(by_currency.items()):
        latest = next((m for m in reversed(months) if m.billed > 0), None)
        mrr = latest.billed if latest else 0
        currencies.append(
            CurrencyMetrics(
                currency=currency,
                mrr=mrr,
                arr=mrr * 12,
                arpu=round(mrr / latest.invoices) if latest and latest.invoices else 0,
                mrr_month=latest.month if latest else months[-1].month,
                months=months,
            )
        )
    # The latest finished month: the current one is still filling up.
    finished = churn(db)[:-1]
    last = finished[-1] if finished else None
    churn_metrics = (
        ChurnMetrics(
            month=last.month,
            cancelled=last.cancelled,
            paying_at_start=last.paying_at_start,
            rate=last.cancelled / last.paying_at_start if last.paying_at_start else None,
        )
        if last
        else None
    )
    ai = None
    if db.execute(text("SELECT app.platform_can('usage.read')")).scalar_one():
        board = ai_costs(db, days=30)
        usd = [b for b in board.businesses if b.currency == "USD"]
        ai = AIMargin(
            days=board.days,
            cost_usd_minor=round(sum(b.credits for b in usd)),
            revenue_usd_minor=sum(b.revenue_monthly_minor for b in usd),
            margin_usd_minor=sum(b.margin_usd_minor or 0 for b in usd),
        )
    return SaasMetrics(currencies=currencies, churn=churn_metrics, ai=ai)


class SuppressedAddress(BaseModel):
    address: str = Field(description="Masked: the first letter and the domain")
    reason: Literal["bounced", "complained"]
    created_at: dt.datetime


class DeliverabilityMonth(BaseModel):
    month: dt.date
    bounced: int
    complained: int


class EmailDeliverability(BaseModel):
    emails_waiting: int
    bounced: int = Field(description="Hard bounces in the last 12 months")
    complained: int = Field(description="Spam complaints in the last 12 months")
    months: list[DeliverabilityMonth]
    recent: list[SuppressedAddress] = Field(description="The latest 50, addresses masked")
    webhook_open: bool = Field(description="Is the provider's bounce webhook switched on")


def mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


@router.get("/email")
def email_deliverability(db: UsageDep) -> EmailDeliverability:
    """Which addresses bounced or complained: they are never mailed again."""
    rows = db.execute(text("SELECT * FROM app.platform_email_suppressions()")).mappings().all()
    waiting = db.execute(text("SELECT (app.platform_health()->>'emails_waiting')::int")).scalar()
    months: dict[dt.date, DeliverabilityMonth] = {}
    for r in rows:
        first = r["created_at"].date().replace(day=1)
        month = months.setdefault(first, DeliverabilityMonth(month=first, bounced=0, complained=0))
        if r["reason"] == "bounced":
            month.bounced += 1
        else:
            month.complained += 1
    return EmailDeliverability(
        emails_waiting=waiting or 0,
        bounced=sum(1 for r in rows if r["reason"] == "bounced"),
        complained=sum(1 for r in rows if r["reason"] == "complained"),
        months=sorted(months.values(), key=lambda m: m.month),
        recent=[
            SuppressedAddress(
                address=mask(r["address"]), reason=r["reason"], created_at=r["created_at"]
            )
            for r in rows[:50]
        ],
        webhook_open=get_settings().email_webhook_secret is not None,
    )


# A city with fewer businesses or people than this is not shown at all (the database enforces the
# same floor, so a caller cannot ask for less).
MIN_PER_CITY = 5


class MapIndustry(BaseModel):
    vertical: str | None = Field(description="The industry; none when it is too few to name")
    total: int


class MapCity(BaseModel):
    city_code: int
    city_name: str
    latitude: float
    longitude: float
    total: int
    industries: list[MapIndustry] = Field(description="Largest first; small ones are 'mixed'")


class BusinessMap(BaseModel):
    min_per_city: int
    businesses: list[MapCity] = Field(description="Cities with an active branch, by business")
    clients: list[MapCity] = Field(description="Cities clients live in, across all businesses")
    without_point: int = Field(description="Cities left out for lack of a known centre")


@router.get("/business-map")
def business_map(db: AdminDep) -> BusinessMap:
    """Where the businesses are and where their clients live, by city, split by industry. Totals
    only: no names, and no city with fewer than five."""
    rows = db.execute(
        text("SELECT * FROM app.platform_business_map(:minimum)"), {"minimum": MIN_PER_CITY}
    ).mappings()
    layers: dict[str, dict[int, dict]] = {"businesses": {}, "clients": {}}
    for row in rows:
        city = layers[row["layer"]].setdefault(
            row["city_code"],
            {
                "name": row["city_name"],
                "point": (row["latitude"], row["longitude"]),
                "industries": [],
            },
        )
        city["industries"].append(MapIndustry(vertical=row["vertical"], total=row["total"]))

    skipped: set[int] = set()

    def cities(layer: str) -> list[MapCity]:
        found = []
        for code, city in layers[layer].items():
            point = city["point"]
            if point[0] is None or point[1] is None:
                skipped.add(code)
                continue
            industries = sorted(city["industries"], key=lambda i: (-i.total, i.vertical or ""))
            found.append(
                MapCity(
                    city_code=code,
                    city_name=city["name"],
                    latitude=point[0],
                    longitude=point[1],
                    total=sum(i.total for i in industries),
                    industries=industries,
                )
            )
        return sorted(found, key=lambda c: (-c.total, c.city_name))

    return BusinessMap(
        min_per_city=MIN_PER_CITY,
        businesses=cities("businesses"),
        clients=cities("clients"),
        without_point=len(skipped),
    )
