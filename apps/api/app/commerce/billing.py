"""Platform billing (simulated, migration 0029): after the free trial, each business gets a
monthly invoice in arrears for the modules it has on, priced like the configurator (core tier by
active clients at the end of the period + modules). With a (test) card on file the invoice is
charged at once; otherwise it stays open until the owner pays it.

Periods run month to month from the day the trial ends (in the business's time zone). One-time
services (setup) are charged with the first invoice."""

import calendar
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.commerce.modules import quote

MAX_PERIODS_PER_RUN = 24  # a business that was never billed catches up at most two years


def add_months(day: date, months: int) -> date:
    """The same day `months` later, clamped to the end of shorter months (Jan 31 → Feb 28)."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Period:
    start: date
    end: date


def periods_due(anchor: date, last_start: date | None, today: date) -> list[Period]:
    """Billing periods that have ended by `today` and were not invoiced yet."""
    due: list[Period] = []
    for index in range(1000):
        start = add_months(anchor, index)
        end = add_months(anchor, index + 1) - timedelta(days=1)
        if end >= today or len(due) >= MAX_PERIODS_PER_RUN:
            break
        if last_start is None or start > last_start:
            due.append(Period(start, end))
    return due


def active_clients_on(conn: Connection, tenant_id: UUID, day: date) -> int:
    return conn.execute(
        text("""
            SELECT count(DISTINCT client_id) FROM app.entitlements
            WHERE tenant_id = :t AND status = 'active' AND :day BETWEEN starts_on AND ends_on
        """),
        {"t": tenant_id, "day": day},
    ).scalar_one()


def bill_businesses(
    conn: Connection, now: datetime | None = None, tenant_id: UUID | None = None
) -> int:
    """Issues the invoices that are due (for every business, or one). Safe to run repeatedly:
    one invoice per period."""
    now = now or datetime.now(UTC)
    tenants = conn.execute(
        text("""
            SELECT t.id, t.time_zone, t.currency, t.trial_ends_at,
                   (SELECT max(period_start) FROM app.platform_invoices i
                    WHERE i.tenant_id = t.id) AS last_start,
                   a.card_last4
            FROM app.tenants t LEFT JOIN app.billing_accounts a ON a.tenant_id = t.id
            WHERE t.trial_ends_at < :now AND (CAST(:tenant AS uuid) IS NULL OR t.id = :tenant)
        """),
        {"now": now, "tenant": tenant_id},
    ).all()
    issued = 0
    for tenant in tenants:
        zone = ZoneInfo(tenant.time_zone)
        today = now.astimezone(zone).date()
        anchor = tenant.trial_ends_at.astimezone(zone).date()
        modules = dict(
            conn.execute(
                text("SELECT module_key, quantity FROM app.tenant_modules WHERE tenant_id = :t"),
                {"t": tenant.id},
            ).all()
        )
        for period in periods_due(anchor, tenant.last_start, today):
            clients = active_clients_on(conn, tenant.id, period.end)
            priced = quote(modules, clients, tenant.currency)
            lines = [{"key": "core", "quantity": 1, "amount": priced.core}] + [
                {"key": key, "quantity": modules[key], "amount": amount}
                for key, amount in priced.lines.items()
            ]
            total = priced.total
            # One-time services (the setup bought in the sign-up journey) ride on the first one.
            if period.start == anchor:
                lines += [
                    {"key": key, "quantity": 1, "amount": amount}
                    for key, amount in priced.once.items()
                ]
                total += sum(priced.once.values())
            charged = tenant.card_last4 is not None
            inserted = conn.execute(
                text("""
                    INSERT INTO app.platform_invoices
                        (tenant_id, period_start, period_end, currency, active_clients, lines,
                         total, status, issued_at, paid_at, card_last4)
                    VALUES (:t, :start, :end, :currency, :clients, CAST(:lines AS jsonb), :total,
                            :status, :now, :paid_at, :last4)
                    ON CONFLICT (tenant_id, period_start) DO NOTHING
                """),
                {
                    "t": tenant.id,
                    "start": period.start,
                    "end": period.end,
                    "currency": tenant.currency,
                    "clients": clients,
                    "lines": json.dumps(lines),
                    "total": total,
                    "status": "paid" if charged else "open",
                    "now": now,
                    "paid_at": now if charged else None,
                    "last4": tenant.card_last4,
                },
            ).rowcount
            issued += inserted
    return issued
