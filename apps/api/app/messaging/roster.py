"""Emailing staff their newly published shifts (the notify-shifts job; see app/jobs.py).

A published shift is emailed once, to the person it belongs to, in one message per person and
business; manual and scheduled publishing look the same here. People can turn the emails off
(`users.email_roster`); their shifts are then marked as handled without sending anything."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
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
from app.messaging.push import PushSender, push_to_user

MAX_LINES = 20
# Edits to a published roster go out as one email once they have been quiet this long (or, when
# someone keeps editing, once the oldest has waited the maximum).
QUIET_PERIOD = timedelta(minutes=15)
MAX_WAIT = timedelta(hours=2)


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


def _deliver(
    conn: Connection,
    sender: Sender | None,
    push: PushSender | None,
    person: Any,
    subject: str,
    body: str,
) -> str:
    """Tells one person: a push to their phone first, then the email as a fallback (when they
    have emails on). Returns "pushed", "emailed", "failed" (email error; try again later) or
    "skipped" (no way to reach them)."""
    if push and push_to_user(conn, push, person["user_id"], subject, body.split("\n\n", 1)[-1]):
        return "pushed"
    if sender and person["email_roster"] and person["email"]:
        try:
            sender.send(Email(to=person["email"], subject=subject, text=body))
        except Exception as error:  # a provider error must not stop the batch
            print(f"roster email to {person['user_id']} failed: {error}")
            return "failed"
        return "emailed"
    return "skipped"


def _counts(sent: int, failed: int, skipped: int, pushed: int, push: PushSender | None) -> dict:
    counts = {"sent": sent, "failed": failed, "skipped": skipped}
    return counts | {"pushed": pushed} if push else counts


def notify_roster(
    conn: Connection,
    sender: Sender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
    push: PushSender | None = None,
) -> dict[str, int]:
    """Tells the people whose shifts were published since the last run, by push when they have
    a phone registered and by email otherwise. Returns the counts of emails sent and failed, and
    of people skipped (switched off, or no way to reach them); with a push sender, also pushed."""
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
    sent = failed = skipped = pushed = 0
    per_tenant: dict[Any, int] = {}
    for (tenant_id, _user), shifts in people.items():
        first = shifts[0]
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
        outcome = _deliver(conn, sender, push, first, subject, body)
        if outcome == "failed":
            failed += 1
            continue  # stays unnotified; the next run tries again until the shifts are over
        if outcome == "emailed":
            sent += 1
            per_tenant[tenant_id] = per_tenant.get(tenant_id, 0) + 1
        elif outcome == "pushed":
            pushed += 1
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
    return _counts(sent, failed, skipped, pushed, push)


def render_changes(
    messages: dict[str, Any],
    business: str,
    name: str | None,
    removed: list[Any],
    changed: list[tuple[Any, Any]],
    time_zone: str,
) -> tuple[str, str]:
    """One email for a person's edited shifts: the ones taken away, and the ones that now read
    differently (before → now)."""
    text_ = messages["rosterChanges"]
    zone = ZoneInfo(time_zone)
    shared = messages["roster"]
    items = [f"{text_['removed']} {_line(shared, row, zone)}" for row in removed]
    items += [
        f"{text_['changed']} {_line(shared, before, zone)} → {text_['arrow']} "
        f"{_line(shared, after, zone)}"
        for before, after in changed
    ]
    values = {"business": business, "name": name or "", "count": str(len(items) - MAX_LINES)}
    lines = [_fill(messages["greeting"], values).replace(" ,", ","), ""]
    lines += [_fill(text_["intro"], values), "", *items[:MAX_LINES]]
    if len(items) > MAX_LINES:
        lines.append(_fill(text_["more"], values))
    lines += ["", _fill(text_["footer"], values)]
    return _fill(text_["subject"], values), "\n".join(lines)


def notify_roster_changes(
    conn: Connection,
    sender: Sender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
    push: PushSender | None = None,
) -> dict[str, int]:
    """Emails the people whose already-announced shifts were edited or removed, one email per
    person once their roster has been quiet for QUIET_PERIOD, covering every edit since: a shift
    edited several times shows only where it started and where it ended up, and a shift put back
    as it was is not mentioned. Returns the counts of emails sent and failed, and of people
    skipped (switched off, no email address, or nothing to tell)."""
    now = now or datetime.now(UTC)
    # Shifts that are over need no email.
    conn.execute(
        text(
            "UPDATE app.shift_changes SET handled_at = :now WHERE handled_at IS NULL"
            " AND before_ends <= :now"
        ),
        {"now": now},
    )
    due = (
        conn.execute(
            text("""
                SELECT tenant_id, user_id FROM app.shift_changes
                WHERE handled_at IS NULL
                GROUP BY tenant_id, user_id
                HAVING max(created_at) <= :now - CAST(:quiet AS interval)
                    OR min(created_at) <= :now - CAST(:wait AS interval)
            """),
            {"now": now, "quiet": QUIET_PERIOD, "wait": MAX_WAIT},
        )
        .mappings()
        .all()
    )
    messages: dict[str, dict[str, Any]] = {}
    sent = failed = skipped = pushed = 0
    per_tenant: dict[Any, int] = {}
    for key in due:
        rows = (
            conn.execute(
                text("""
                    SELECT c.id, c.shift_id, c.before_starts, c.before_ends, c.before_branch,
                           c.before_position, c.created_at
                    FROM app.shift_changes c
                    WHERE c.tenant_id = :t AND c.user_id = :u AND c.handled_at IS NULL
                    ORDER BY c.created_at
                    FOR UPDATE OF c SKIP LOCKED
                """),
                {"t": key["tenant_id"], "u": key["user_id"]},
            )
            .mappings()
            .all()
        )
        if not rows:
            continue
        first: dict[Any, Any] = {}
        for row in rows:
            first.setdefault(row["shift_id"], row)  # where each shift started
        current = {
            row["id"]: row
            for row in conn.execute(
                text("""
                    SELECT s.id, s.starts_at, s.ends_at, s.position, l.name AS branch
                    FROM app.shifts s
                    JOIN app.locations l ON l.tenant_id = s.tenant_id AND l.id = s.location_id
                    WHERE s.tenant_id = :t AND s.user_id = :u AND s.published_at IS NOT NULL
                      AND s.id = ANY(CAST(:ids AS uuid[]))
                """),
                {"t": key["tenant_id"], "u": key["user_id"], "ids": [str(i) for i in first]},
            ).mappings()
        }
        removed: list[Any] = []
        changed: list[tuple[Any, Any]] = []
        for shift_id, before in first.items():
            after = current.get(shift_id)
            start = {
                "starts_at": before["before_starts"],
                "ends_at": before["before_ends"],
                "branch": before["before_branch"],
                "position": before["before_position"],
            }
            if after is None:
                removed.append(start)
            elif after["ends_at"] > now and any(
                start[field] != after[field]
                for field in ("starts_at", "ends_at", "branch", "position")
            ):
                changed.append((start, after))
        removed.sort(key=lambda row: row["starts_at"])
        changed.sort(key=lambda pair: pair[0]["starts_at"])
        person = (
            conn.execute(
                text("""
                    SELECT u.id AS user_id, t.name AS business, t.time_zone,
                           COALESCE(u.locale, t.locale) AS locale,
                           u.email, u.full_name, u.email_roster
                    FROM app.tenants t, app.users u
                    WHERE t.id = :t AND u.id = :u
                """),
                {"t": key["tenant_id"], "u": key["user_id"]},
            )
            .mappings()
            .first()
        )
        if person and (removed or changed):
            locale = person["locale"] if person["locale"] in ("he", "en") else "en"
            if locale not in messages:
                messages[locale] = load_messages(locale, messages_dir)
            subject, body = render_changes(
                messages[locale],
                person["business"],
                (person["full_name"] or "").split(" ")[0] or None,
                removed,
                changed,
                person["time_zone"],
            )
            outcome = _deliver(conn, sender, push, person, subject, body)
            if outcome == "failed":
                failed += 1
                continue  # stays pending; the next run tries again
            if outcome == "emailed":
                sent += 1
                per_tenant[key["tenant_id"]] = per_tenant.get(key["tenant_id"], 0) + 1
            elif outcome == "pushed":
                pushed += 1
            else:
                skipped += 1
        else:
            skipped += 1
        conn.execute(
            text(
                "UPDATE app.shift_changes SET handled_at = :now"
                " WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"now": now, "ids": [str(row["id"]) for row in rows]},
        )
    for tenant_id, count in per_tenant.items():
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (:t, 'messages', :n, CAST(:details AS jsonb), 'roster_change_emails')
            """),
            {"t": tenant_id, "n": count, "details": EMAIL_DETAILS},
        )
    return _counts(sent, failed, skipped, pushed, push)
