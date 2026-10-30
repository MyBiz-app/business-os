"""Jobs that send things out or move data: shifts, messages, emails, files, social."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.core.tenant_scope import tenant_scope
from app.messaging import outbox
from app.messaging.announcements import send_announcements as run_announcements
from app.messaging.email import (
    send_emails,
    sender_from_settings,
)
from app.messaging.owner_alerts import alert_owners
from app.messaging.payroll_notices import notify_payslips_ready, remind_payroll
from app.messaging.push import push_sender_from_settings
from app.messaging.roster import notify_roster, notify_roster_changes
from app.providers.choice import choose
from app.providers.storage import tenant_key


def _publish_moment(row: dict, now: datetime) -> tuple[datetime, datetime]:
    """The latest moment at or before `now` the business's roster is due out, and the end of the
    stretch it covers: daily through tomorrow, weekly seven days, monthly until the same day of
    the next month. Both are UTC."""
    zone = ZoneInfo(row["time_zone"])
    local = now.astimezone(zone)
    at = row["shifts_publish_time"]
    cadence = row["shifts_publish_cadence"]
    day = local.date()
    if cadence == "weekly":
        day -= timedelta(days=(day.weekday() - row["shifts_publish_weekday"]) % 7)
    elif cadence == "monthly":
        if day.day < row["shifts_publish_day"]:
            day = (day.replace(day=1) - timedelta(days=1)).replace(day=1)
        day = day.replace(day=row["shifts_publish_day"])
    if datetime.combine(day, at, zone) > local:
        day -= {
            "daily": timedelta(days=1),
            "weekly": timedelta(days=7),
            "monthly": timedelta(days=28),
        }[cadence]
        if cadence == "monthly":
            day = day.replace(day=row["shifts_publish_day"])
    if cadence == "daily":
        end = day + timedelta(days=2)
    elif cadence == "weekly":
        end = day + timedelta(days=7)
    else:
        end = (day.replace(day=1) + timedelta(days=32)).replace(day=row["shifts_publish_day"])
    due = datetime.combine(day, at, zone).astimezone(UTC)
    return due, datetime.combine(end, time.min, zone).astimezone(UTC)


def publish_shifts(conn: Connection, now: datetime | None = None) -> int:
    """Publishes the draft shifts of every business whose roster is due (once per due moment).
    Run hourly. Returns how many shifts became visible."""
    now = now or datetime.now(UTC)
    published = 0
    rows = conn.execute(
        text("""
            SELECT id, time_zone, shifts_publish_cadence, shifts_publish_weekday,
                   shifts_publish_day, shifts_publish_time, shifts_last_auto_published_at
            FROM app.tenants WHERE shifts_publish_auto AND closed_at IS NULL
        """)
    ).mappings()
    for row in list(rows):
        with tenant_scope(conn, row["id"]):
            due, end = _publish_moment(dict(row), now)
            last = row["shifts_last_auto_published_at"]
            if last is not None and last >= due:
                continue
            published += conn.execute(
                text("""
                    UPDATE app.shifts SET published_at = :now
                    WHERE tenant_id = :tenant AND published_at IS NULL AND starts_at < :end
                """),
                {"now": now, "tenant": row["id"], "end": end},
            ).rowcount
            conn.execute(
                text("UPDATE app.tenants SET shifts_last_auto_published_at = :now WHERE id = :id"),
                {"now": now, "id": row["id"]},
            )
    return published


def send_messages(conn: Connection) -> dict[str, int]:
    return outbox.send_messages(conn)


def send_announcements(conn: Connection) -> dict[str, int]:
    return run_announcements(conn, sender_from_settings(), push_sender_from_settings())


def issue_documents(conn: Connection) -> dict[str, int]:
    return outbox.issue_documents(conn)


def notify_shifts(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    push = push_sender_from_settings()
    if sender is None and push is None:
        return "no email or push provider configured; nothing sent"
    published = notify_roster(conn, sender, push=push)
    edits = notify_roster_changes(conn, sender, push=push)
    return published | {f"changes_{key}": value for key, value in edits.items()}


def remind_payroll_job(conn: Connection) -> dict[str, int] | str:
    push = push_sender_from_settings()
    if push is None:
        return "no push provider configured; nothing sent"
    return remind_payroll(conn, push)


def alert_owners_job(conn: Connection) -> dict[str, int] | str:
    push = push_sender_from_settings()
    if push is None:
        return "no push provider configured; nothing sent"
    return alert_owners(conn, push)


def notify_payslips(conn: Connection) -> dict[str, int] | str:
    push = push_sender_from_settings()
    if push is None:
        return "no push provider configured; nothing sent"
    return notify_payslips_ready(conn, push)


def send_notification_emails(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    push = push_sender_from_settings()
    if sender is None and push is None:
        return "no email or push provider configured; nothing sent"
    return send_emails(conn, sender, push=push)


MOVE_BATCH = 100  # documents per run, so one run stays short; run again until it reports 0


def move_files(conn: Connection, batch: int = MOVE_BATCH) -> dict[str, int] | str:
    """Moves documents still kept in the database to the object store (T80), a batch per run.
    The key is the document's own, so a run that fails half-way is simply run again."""
    storage = choose(conn, None, "storage").instance
    if storage.in_database:
        return "storage provider keeps files in the database; nothing to move"
    rows = conn.execute(
        text("""
            SELECT id, tenant_id, client_id, content_type, content FROM app.client_documents
            WHERE content IS NOT NULL ORDER BY created_at LIMIT :batch
        """),
        {"batch": batch},
    ).mappings()
    moved = 0
    for row in list(rows):
        key = tenant_key(row["tenant_id"], "documents", row["client_id"], row["id"])
        storage.put(key, bytes(row["content"]), row["content_type"])
        conn.execute(
            text(
                "UPDATE app.client_documents SET storage_key = :key, content = NULL WHERE id = :id"
            ),
            {"key": key, "id": row["id"]},
        )
        moved += 1
    left = conn.execute(
        text("SELECT count(*) FROM app.client_documents WHERE content IS NOT NULL")
    ).scalar_one()
    return {"moved": moved, "left": left}


def run_ai_tasks(conn: Connection) -> dict[str, int]:
    """Runs the scheduled AI agent tasks whose time has come (app/ai/task_runner.py)."""
    from app.ai.task_runner import run_due_tasks

    return run_due_tasks(conn)


def sync_social(conn: Connection) -> dict[str, int]:
    """Reads the latest numbers of every connected social account (the content studio). One
    account failing (a network down, a token the owner revoked) does not stop the others."""
    from app.social.sync import sync_account

    rows = conn.execute(
        text("""
            SELECT a.id, a.tenant_id FROM app.social_accounts a
            JOIN app.tenants t ON t.id = a.tenant_id
            WHERE a.status = 'connected' AND t.closed_at IS NULL ORDER BY a.tenant_id
        """)
    ).all()
    synced = 0
    for account_id, tenant_id in rows:
        with tenant_scope(conn, tenant_id):
            sync_account(conn, tenant_id, account_id)
            synced += 1
    return {"synced": synced, "failed": len(rows) - synced}
