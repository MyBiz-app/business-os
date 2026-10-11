"""Emailing staff their newly published shifts (the notify-shifts job; see app/jobs.py).

A published shift is emailed once, to the person it belongs to, in one message per person and
business; manual and scheduled publishing look the same here. People can turn the emails off
(`users.email_roster`); their shifts are then marked as handled without sending anything."""

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.messaging.email import (
    EMAIL_DETAILS,
    MESSAGES_DIR,
    Email,
    Sender,
    _fill,
    load_messages,
)

MAX_LINES = 20


def _line(messages: dict[str, Any], row: Any, zone: ZoneInfo) -> str:
    start, end = row["starts_at"].astimezone(zone), row["ends_at"].astimezone(zone)
    return _fill(
        messages["line"],
        {
            "day": f"{messages['weekdays'][start.weekday()]} {start:%d/%m}",
            "from": f"{start:%H:%M}",
            "to": f"{end:%H:%M}",
            "branch": row["branch"],
            "position": f" · {row['position']}" if row["position"] else "",
        },
    )


def render_roster(
    messages: dict[str, Any], business: str, name: str | None, shifts: list[Any], time_zone: str
) -> tuple[str, str]:
    values = {"business": business, "name": name or "", "count": str(len(shifts) - MAX_LINES)}
    zone = ZoneInfo(time_zone)
    lines = [_fill(messages["greeting"], values).replace(" ,", ","), ""]
    lines += [_fill(messages["roster"]["intro"], values), ""]
    lines += [_line(messages["roster"], row, zone) for row in shifts[:MAX_LINES]]
    if len(shifts) > MAX_LINES:
        lines.append(_fill(messages["roster"]["more"], values))
    lines += ["", _fill(messages["roster"]["footer"], values)]
    return _fill(messages["roster"]["subject"], values), "\n".join(lines)


def notify_roster(
    conn: Connection,
    sender: Sender,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
) -> dict[str, int]:
    """Emails the people whose shifts were published since the last run. Returns the counts of
    emails sent and failed, and of people skipped (switched off, or no email address)."""
    now = now or datetime.now(UTC)
    # Shifts that are already over need no email.
    conn.execute(
        text("""
            UPDATE app.shifts SET notified_at = :now
            WHERE published_at IS NOT NULL AND notified_at IS NULL AND ends_at <= :now
        """),
        {"now": now},
    )
    rows = (
        conn.execute(
            text("""
                SELECT s.id, s.tenant_id, s.user_id, s.starts_at, s.ends_at, s.position,
                       l.name AS branch, t.name AS business, t.time_zone,
                       COALESCE(u.locale, t.locale) AS locale,
                       u.email, u.full_name, u.email_roster
                FROM app.shifts s
                JOIN app.tenants t ON t.id = s.tenant_id
                JOIN app.locations l ON l.tenant_id = s.tenant_id AND l.id = s.location_id
                JOIN app.users u ON u.id = s.user_id
                WHERE s.published_at IS NOT NULL AND s.notified_at IS NULL
                ORDER BY s.starts_at
                FOR UPDATE OF s SKIP LOCKED
            """)
        )
        .mappings()
        .all()
    )
    people: dict[tuple[Any, Any], list[Any]] = defaultdict(list)
    for row in rows:
        people[(row["tenant_id"], row["user_id"])].append(row)
    messages: dict[str, dict[str, Any]] = {}
    sent = failed = skipped = 0
    per_tenant: dict[Any, int] = {}
    for (tenant_id, _user), shifts in people.items():
        first = shifts[0]
        if first["email_roster"] and first["email"]:
            locale = first["locale"] if first["locale"] in ("he", "en") else "en"
            if locale not in messages:
                messages[locale] = load_messages(locale, messages_dir)
            subject, body = render_roster(
                messages[locale],
                first["business"],
                (first["full_name"] or "").split(" ")[0] or None,
                shifts,
                first["time_zone"],
            )
            try:
                sender.send(Email(to=first["email"], subject=subject, text=body))
            except Exception as error:  # a provider error must not stop the batch
                failed += 1
                print(f"roster email to {first['user_id']} failed: {error}")
                continue  # stays unnotified; the next run tries again until the shifts are over
            sent += 1
            per_tenant[tenant_id] = per_tenant.get(tenant_id, 0) + 1
        else:
            skipped += 1
        conn.execute(
            text("UPDATE app.shifts SET notified_at = :now WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"now": now, "ids": [str(row["id"]) for row in shifts]},
        )
    for tenant_id, count in per_tenant.items():
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (:t, 'messages', :n, CAST(:details AS jsonb), 'roster_emails')
            """),
            {"t": tenant_id, "n": count, "details": EMAIL_DETAILS},
        )
    return {"sent": sent, "failed": failed, "skipped": skipped}
