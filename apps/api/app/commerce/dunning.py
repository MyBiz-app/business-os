"""Collecting unpaid MyBiz invoices (go-live GL20): reminders, then read-only, then suspension.

The clock starts when the oldest open invoice is issued (invoices are due on issue). With the
defaults a business gets an email on days 0, 3 and 7, turns read-only on day 14 (it sees
everything, changes nothing) and is suspended on day 30 (nobody signs in; nothing is deleted).
The days, and the whole sequence, are set from the MyBiz console (`dunning_settings`); a grace
extension from the console holds off read-only and suspension until it ends.

The API enforces `tenants.billing_state` (see app/api/deps.py); this job moves it. Paying the last
open invoice lifts it at once (migration 0123, `pay_platform_invoice`)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.messaging.contact_emails import resolve_email
from app.messaging.email import Email, Sender, load_all_messages, sender_from_settings

# `dunning_events.stage`: a reminder day is stored as itself; the two state changes as these.
STAGE_READ_ONLY = -1
STAGE_SUSPENDED = -2


@dataclass(frozen=True)
class Policy:
    enabled: bool
    reminder_days: tuple[int, ...]
    read_only_after_days: int
    suspend_after_days: int


def load_policy(conn: Connection) -> Policy:
    row = conn.execute(text("SELECT * FROM app.dunning_settings")).mappings().one()
    return Policy(
        enabled=row["enabled"],
        reminder_days=tuple(sorted(set(row["reminder_days"]))),
        read_only_after_days=row["read_only_after_days"],
        suspend_after_days=row["suspend_after_days"],
    )


def state_for(days_overdue: int, policy: Policy, in_grace: bool) -> str:
    """The state a business with an invoice `days_overdue` days old is in."""
    if not policy.enabled or in_grace:
        return "active"
    if days_overdue >= policy.suspend_after_days:
        return "suspended"
    if days_overdue >= policy.read_only_after_days:
        return "read_only"
    return "active"


def _day(value: datetime, time_zone: str, locale: str) -> str:
    local = value.astimezone(ZoneInfo(time_zone))
    return local.strftime("%d/%m/%Y")


def _money(amount: int, currency: str) -> str:
    return f"{amount / 100:,.2f} {currency}"


def _email(conn: Connection, tenant: Any, invoice: Any, kind: str, policy: Policy) -> Email | None:
    to = resolve_email(conn, tenant.id, "billing")
    if to is None:
        return None
    locale = tenant.locale if tenant.locale in ("he", "en") else "en"
    messages = load_all_messages(locale)["dunningEmail"]
    values = {
        "business": tenant.name,
        "number": str(invoice.number),
        "amount": _money(invoice.total, invoice.currency),
        "readOnlyDate": _day(
            invoice.issued_at + timedelta(days=policy.read_only_after_days),
            tenant.time_zone,
            locale,
        ),
        "suspendDate": _day(
            invoice.issued_at + timedelta(days=policy.suspend_after_days),
            tenant.time_zone,
            locale,
        ),
    }

    def fill(template: str) -> str:
        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    return Email(
        to=to,
        subject=fill(messages["subject"][kind]),
        text="\n".join(
            [messages["greeting"], "", fill(messages["body"][kind]), "", messages["footer"]]
        ),
        locale=locale,
        details=(
            (messages["details"]["invoice"], str(invoice.number)),
            (messages["details"]["amount"], values["amount"]),
        ),
        kind="billing",
    )


def run_dunning(
    conn: Connection, now: datetime | None = None, sender: Sender | None = None
) -> dict[str, int]:
    """Sends the reminders that are due and moves each business to its billing state.
    Safe to run repeatedly: a reminder goes out once per invoice and day."""
    now = now or datetime.now(UTC)
    if sender is None:
        sender = sender_from_settings()
    policy = load_policy(conn)
    counts = {"reminders": 0, "read_only": 0, "suspended": 0, "restored": 0}
    tenants = conn.execute(
        text("""
            SELECT t.id, t.name, t.locale, t.time_zone, t.billing_state, t.billing_grace_until
            FROM app.tenants t
            WHERE t.closed_at IS NULL AND (
                t.billing_state <> 'active'
                OR EXISTS (SELECT 1 FROM app.platform_invoices i
                           WHERE i.tenant_id = t.id AND i.status = 'open')
            )
        """)
    ).all()
    for tenant in tenants:
        invoices = conn.execute(
            text("""
                SELECT id, number, currency, total, issued_at FROM app.platform_invoices
                WHERE tenant_id = :t AND status = 'open' ORDER BY issued_at
            """),
            {"t": tenant.id},
        ).all()
        if not invoices:
            new_state, days = "active", 0
        else:
            oldest = invoices[0]
            days = (now - oldest.issued_at).days
            in_grace = tenant.billing_grace_until is not None and tenant.billing_grace_until > now
            new_state = state_for(days, policy, in_grace)
            if policy.enabled:
                _remind(conn, sender, tenant, oldest, days, new_state, policy, counts)
        if new_state != tenant.billing_state:
            conn.execute(
                text("UPDATE app.tenants SET billing_state = :s WHERE id = :t"),
                {"s": new_state, "t": tenant.id},
            )
            key = {"read_only": "read_only", "suspended": "suspended", "active": "restored"}
            counts[key[new_state]] += 1
    return counts


def _remind(
    conn: Connection,
    sender: Sender | None,
    tenant: Any,
    invoice: Any,
    days: int,
    new_state: str,
    policy: Policy,
    counts: dict[str, int],
) -> None:
    """One email per run and invoice: the one for turning read-only or suspended, else the latest
    reminder day reached (a job that was down for a week sends one reminder, not three)."""
    recorded = set(
        conn.execute(
            text("SELECT stage FROM app.dunning_events WHERE invoice_id = :i"),
            {"i": invoice.id},
        ).scalars()
    )
    pending = [d for d in policy.reminder_days if d <= days and d not in recorded]
    mail: tuple[int, str] | None = None
    for state, stage, kind in (
        (("suspended", STAGE_SUSPENDED, "suspended")),
        (("read_only", STAGE_READ_ONLY, "readOnly")),
    ):
        if new_state == state and stage not in recorded:
            mail = (stage, kind)
            break
    if mail is None and pending:
        mail = (max(pending), "reminder")
    emailed = False
    if mail is not None and sender is not None:
        email = _email(conn, tenant, invoice, mail[1], policy)
        if email is not None:
            try:
                sender.send(email)
                emailed = True
            except Exception as error:  # a provider error must not stop the run; retry next time
                print(f"dunning email for {tenant.id} failed: {error}")
                return
    stages = {d: False for d in pending}
    if mail is not None:
        stages[mail[0]] = emailed
    for stage, was_emailed in stages.items():
        conn.execute(
            text("""
                INSERT INTO app.dunning_events (invoice_id, stage, emailed)
                VALUES (:i, :stage, :emailed) ON CONFLICT DO NOTHING
            """),
            {"i": invoice.id, "stage": stage, "emailed": was_emailed},
        )
    if emailed:
        counts["reminders"] += 1
