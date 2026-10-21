"""The market researcher's tools (slice C4): our own price list, the competitors to compare with,
and saving a price comparison as a report.

The researcher never changes a price. It reads our price list (the modules and the website
service), reads competitor prices from public pages (web search, when the team has switched it
on) and saves a report. The server, not the model, works out where we are dearer than the
cheapest competitor, so the red marks in a report can be trusted. A competitor price must come
with an https link and the date it was read."""

import datetime as dt
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commerce.modules import MODULES
from app.websites.pricing import PRICES as WEBSITE_PRICES

COMPETITORS_FILE = Path(__file__).with_name("market_competitors.json")
CURRENCIES = ("ILS", "USD", "EUR")
MAX_ROWS = 200


def competitors() -> list[dict[str, str]]:
    return json.loads(COMPETITORS_FILE.read_text(encoding="utf-8"))["competitors"]


def our_items() -> dict[str, dict[str, int]]:
    """item -> currency -> monthly price in minor units: every module a business can buy and the
    monthly part of each website product."""
    items = {
        key: dict(module.prices)
        for key, module in MODULES.items()
        if module.available and module.billing == "monthly"
    }
    for product, by_currency in WEBSITE_PRICES.items():
        items[f"website_{product}"] = {c: monthly for c, (_setup, monthly) in by_currency.items()}
    return items


def our_prices(_db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit": "monthly price in minor units (cents or agorot) per currency",
        "items": [{"item": item, "prices": prices} for item, prices in our_items().items()],
    }


def competitor_list(_db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    return {"competitors": competitors()}


def _row(raw: dict[str, Any], items: dict[str, dict[str, int]], today: dt.date) -> dict[str, Any]:
    item, currency = str(raw["item"]), str(raw["currency"])
    if item not in items:
        raise ValueError(f"unknown item {item}")
    if currency not in CURRENCIES or currency not in items[item]:
        raise ValueError(f"unsupported currency {currency}")
    price = int(raw["price_minor"])
    if price <= 0:
        raise ValueError("a competitor price must be positive")
    url = str(raw["source_url"])
    if urlparse(url).scheme != "https" or not urlparse(url).netloc:
        raise ValueError("every price needs an https source link")
    checked = dt.date.fromisoformat(str(raw["checked_on"]))
    if checked > today:
        raise ValueError("checked_on is in the future")
    competitor = str(raw["competitor"]).strip()[:80]
    if not competitor:
        raise ValueError("every price needs the competitor's name")
    return {
        "item": item,
        "competitor": competitor,
        "currency": currency,
        "price_minor": price,
        "source_url": url[:500],
        "checked_on": checked.isoformat(),
        "note": str(raw.get("note") or "")[:200],
    }


def compare(rows: list[dict[str, Any]], today: dt.date) -> dict[str, Any]:
    """Our price against the cheapest competitor, per item and currency. `pricier` is the red
    mark: we cost more than the cheapest competitor found."""
    items = our_items()
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError(f"send between 1 and {MAX_ROWS} competitor prices")
    clean = [_row(r, items, today) for r in rows]
    comparison: list[dict[str, Any]] = []
    for item, currency in sorted({(r["item"], r["currency"]) for r in clean}):
        cheapest = min(
            (r for r in clean if r["item"] == item and r["currency"] == currency),
            key=lambda r: r["price_minor"],
        )
        ours = items[item][currency]
        comparison.append(
            {
                "item": item,
                "currency": currency,
                "ours_minor": ours,
                "cheapest_minor": cheapest["price_minor"],
                "cheapest_competitor": cheapest["competitor"],
                "gap_percent": round((ours - cheapest["price_minor"]) * 100 / ours, 1),
                "pricier": ours > cheapest["price_minor"],
            }
        )
    return {"comparison": comparison, "prices": clean}


def save_market_report(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    title = str(args["title"]).strip()[:120]
    summary = str(args["summary"]).strip()[:2000]
    if not title or not summary:
        raise ValueError("a report needs a title and a summary")
    body = compare(list(args["rows"]), dt.date.today())
    sources = sorted({r["source_url"] for r in body["prices"]})
    report_id = db.execute(
        text("SELECT app.platform_ai_report_add('market', :title, :summary, CAST(:body AS jsonb))"),
        {"title": title, "summary": summary, "body": json.dumps(body)},
    ).scalar_one()
    return {
        "report_id": str(report_id),
        "sources": len(sources),
        "pricier": [
            f"{c['item']} ({c['currency']}): {c['gap_percent']}% above {c['cheapest_competitor']}"
            for c in body["comparison"]
            if c["pricier"]
        ],
        "note": "Saved. A person decides on any price change.",
    }
