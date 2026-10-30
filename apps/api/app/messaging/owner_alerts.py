"""Phone alerts for the business owner (app sweep slice 14, improvement B14).

An hourly job (`alert-owners`) does two things:

1. It queues what clients did on their own since the last run in `app.owner_push_events`: booked,
   cancelled, joined a waitlist, joined the business through the app, or left an enquiry. Each
   event is unique, so running the job twice never queues or sends it twice. Things the team did
   itself (a booking made by staff) are not queued: nobody needs a push about their own action.
2. It sends each owner one push per business with the counts of what is waiting, in the owner's
   language, skipping the kinds the owner switched off and holding everything back during the
   business's quiet hours (22:00 to 07:00 local time). Queued events wait for the morning.

An event that nobody could be told about (no phone registered, all kinds off) is still marked
as sent, so the queue does not grow. Only owners are alerted; branch-scoped staff are not."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from app.messaging.email import MESSAGES_DIR, _fill, load_messages
from app.messaging.push import PushSender, push_to_user

KINDS = ("booking_new", "booking_cancelled", "waitlist_joined", "client_joined", "lead_new")
QUIET_FROM_HOUR = 22
QUIET_UNTIL_HOUR = 7
LOOKBACK = timedelta(hours=24)  # what a run looks back on; gaps of the scheduler stay covered
EXPIRES = timedelta(hours=36)  # a waiting event older than this is dropped, not sent

_COLLECT = {
    "booking_new": """
        SELECT b.tenant_id, b.id, b.created_at
        FROM app.bookings b
        JOIN app.clients c ON c.tenant_id = b.tenant_id AND c.id = b.client_id
        WHERE b.created_at > :since AND c.user_id IS NOT NULL AND b.created_by = c.user_id
          AND b.waitlisted_at IS NULL
    """,
    "booking_cancelled": """
        SELECT b.tenant_id, b.id, b.cancelled_at
        FROM app.bookings b
        JOIN app.clients c ON c.tenant_id = b.tenant_id AND c.id = b.client_id
        WHERE b.cancelled_at > :since AND c.user_id IS NOT NULL AND b.created_by = c.user_id
          AND b.waitlisted_at IS NULL
    """,
    "waitlist_joined": """
        SELECT b.tenant_id, b.id, b.waitlisted_at
        FROM app.bookings b
        JOIN app.clients c ON c.tenant_id = b.tenant_id AND c.id = b.client_id
        WHERE b.waitlisted_at > :since AND c.user_id IS NOT NULL AND b.created_by = c.user_id
    """,
    "client_joined": """
        SELECT c.tenant_id, c.id, c.created_at
        FROM app.clients c
        WHERE c.created_at > :since AND c.user_id IS NOT NULL
    """,
    "lead_new": """
        SELECT l.tenant_id, l.id, l.created_at
        FROM app.leads l
        WHERE l.created_at > :since AND l.source = 'form'
    """,
}


def queue_events(conn: Connection, now: datetime) -> int:
    """Adds the events of the last day that are not queued yet; returns how many were new."""
    added = 0
    for kind, select in _COLLECT.items():
        added += conn.execute(
            text(f"""
                INSERT INTO app.owner_push_events (tenant_id, kind, ref_id, occurred_at)
                SELECT e.tenant_id, CAST(:kind AS text), e.id, e.at
                FROM ({select}) AS e(tenant_id, id, at)
                JOIN app.tenants t ON t.id = e.tenant_id AND t.closed_at IS NULL
                ON CONFLICT (tenant_id, kind, ref_id) DO NOTHING
            """),
            {"kind": kind, "since": now - LOOKBACK},
        ).rowcount
    return added


def _quiet(local_hour: int) -> bool:
    return local_hour >= QUIET_FROM_HOUR or local_hour < QUIET_UNTIL_HOUR


def _messages(cache: dict[str, dict[str, Any]], messages_dir: Path, locale: str | None):
    code = locale if locale in ("he", "en") else "en"
    if code not in cache:
        cache[code] = load_messages(code, messages_dir)
    return cache[code]["ownerAlert"]


def alert_owners(
    conn: Connection,
    push: PushSender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
) -> dict[str, int]:
    """Queues new events and pushes the waiting ones. Returns the events queued, the businesses
    alerted and the pushes sent."""
    now = now or datetime.now(UTC)
    queued = queue_events(conn, now)
    # Anything too old to still matter is closed without a push.
    conn.execute(
        text(
            "UPDATE app.owner_push_events SET sent_at = :now "
            "WHERE sent_at IS NULL AND occurred_at < :cutoff"
        ),
        {"now": now, "cutoff": now - EXPIRES},
    )
    if push is None:
        return {"queued": queued, "businesses": 0, "pushed": 0}
    tenants = (
        conn.execute(
            text("""
                SELECT t.id, t.name, t.time_zone,
                       extract(hour FROM CAST(:now AS timestamptz) AT TIME ZONE t.time_zone)::int
                           AS local_hour
                FROM app.tenants t
                WHERE EXISTS (SELECT 1 FROM app.owner_push_events e
                              WHERE e.tenant_id = t.id AND e.sent_at IS NULL)
            """),
            {"now": now},
        )
        .mappings()
        .all()
    )
    cache: dict[str, dict[str, Any]] = {}
    businesses = pushed = 0
    for tenant in tenants:
        if _quiet(tenant["local_hour"]):
            continue
        counts = _waiting_counts(conn, tenant["id"])
        owners = conn.execute(
            text("""
                SELECT m.user_id, u.locale
                FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                WHERE m.tenant_id = :t AND m.role = 'owner'
            """),
            {"t": tenant["id"]},
        ).all()
        sent_any = False
        for owner in owners:
            off = set(
                conn.execute(
                    text(
                        "SELECT kind FROM app.owner_push_prefs "
                        "WHERE tenant_id = :t AND user_id = :u AND NOT enabled"
                    ),
                    {"t": tenant["id"], "u": owner.user_id},
                ).scalars()
            )
            wanted = {kind: n for kind, n in counts.items() if kind not in off and n}
            if not wanted:
                continue
            messages = _messages(cache, messages_dir, owner.locale)
            body = " · ".join(
                _fill(messages[kind], {"count": str(wanted[kind])})
                for kind in KINDS
                if kind in wanted
            )
            title = _fill(messages["title"], {"business": tenant["name"]})
            if push_to_user(conn, push, owner.user_id, title, body, tenant_id=tenant["id"]):
                pushed += 1
                sent_any = True
        businesses += 1 if sent_any else 0
        conn.execute(
            text(
                "UPDATE app.owner_push_events SET sent_at = :now "
                "WHERE tenant_id = :t AND sent_at IS NULL"
            ),
            {"now": now, "t": tenant["id"]},
        )
    return {"queued": queued, "businesses": businesses, "pushed": pushed}


def _waiting_counts(conn: Connection, tenant_id: UUID) -> dict[str, int]:
    rows = conn.execute(
        text(
            "SELECT kind, count(*) FROM app.owner_push_events "
            "WHERE tenant_id = :t AND sent_at IS NULL GROUP BY kind"
        ),
        {"t": tenant_id},
    ).all()
    return {kind: n for kind, n in rows}
