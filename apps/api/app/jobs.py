"""Background jobs, run on a schedule (see .github/workflows/jobs-staging.yml).

    uv run python -m app.jobs extend-series [--database-url URL]
    uv run python -m app.jobs remind-sessions
    uv run python -m app.jobs remind-plans
    uv run python -m app.jobs remind-payroll  (daily: owners are reminded on the 1st and 5th)
    uv run python -m app.jobs notify-payslips (hourly: "your payslip is ready" after an approval)
    uv run python -m app.jobs send-emails     (needs API_EMAIL_PROVIDER; see app/messaging/email.py)
    uv run python -m app.jobs message-reminders (WhatsApp copies of today's reminders, simulated)
    uv run python -m app.jobs bill-businesses (simulated platform billing; app/commerce/billing.py)
    uv run python -m app.jobs dunning         (unpaid MyBiz invoices: reminders, read-only, hold)
    uv run python -m app.jobs notify-shifts    (emails staff new and edited published shifts)
    uv run python -m app.jobs publish-shifts  (hourly: the shifts roster goes out on schedule)
    uv run python -m app.jobs send-messages   (the outbox, through each business's provider)
    uv run python -m app.jobs send-announcements (the broadcast center: email, push, pop-ups)
    uv run python -m app.jobs answer-whatsapp (AI replies to clients' WhatsApp messages; idle
                                               until a real WhatsApp provider fills the inbox)
    uv run python -m app.jobs issue-documents (receipts to each business's invoicing provider)
    uv run python -m app.jobs delete-closed-businesses [--apply] (dry run unless --apply)
    uv run python -m app.jobs sync-social     (reads the numbers of connected social accounts)
    uv run python -m app.jobs move-files      (documents kept in the database → the object store)
    uv run python -m app.jobs rotate-secrets [--apply] (re-encrypts with the newest key; manual)
    uv run python -m app.jobs run-daily       (every daily job in turn, for a cron service)
    uv run python -m app.jobs run-hourly      (every hourly job in turn)
    uv run python -m app.jobs check-jobs      (fails when a scheduled job is late, and alerts the
                                               MyBiz owners' phones and email)
    uv run python -m app.jobs test-alert      (sends a test alert, to check the phones receive it)

Every run is recorded in app.job_runs (started, finished, ok, result), so a job that stopped
running or keeps failing is noticed by check-jobs (.github/workflows/check-jobs-staging.yml).

Jobs connect with the migration (owner) login but switch to the `app_jobs` role (jobs_engine):
it works across all businesses and can read and write rows, but cannot change the schema or
truncate a table. They must only do system work that needs no user's permission."""

import argparse
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, Engine, create_engine, event, text

from app.commerce.billing import bill_businesses
from app.commerce.dunning import run_dunning
from app.core.brand import NAME
from app.core.config import get_settings
from app.core.retention import CLOSED_BUSINESS_GRACE_DAYS
from app.core.tenant_scope import Tally, start_tally, tenant_scope
from app.files import forget, purge_expired_files
from app.messaging import outbox
from app.messaging.alerts import AlertResult, alert_team
from app.messaging.announcements import send_announcements as run_announcements
from app.messaging.email import (
    MESSAGES_DIR,
    load_messages,
    render,
    send_emails,
    sender_from_settings,
)
from app.messaging.payroll_notices import notify_payslips_ready, remind_payroll
from app.messaging.push import push_sender_from_settings
from app.messaging.roster import notify_roster, notify_roster_changes
from app.messaging.whatsapp_ai import answer_inbox
from app.providers.choice import choose
from app.providers.storage import tenant_key
from app.schedule.scheduling import weekly_occurrences
from app.secrets_rotation import rotate_secrets

LOCK_PREFIX = "bos-job:"  # advisory-lock key of a job: one run of each at a time
HORIZON_DAYS = 12 * 7  # open-ended series always have this much schedule ahead


def extend_series(conn: Connection, now: datetime | None = None) -> int:
    """Adds occurrences to open-ended series up to the horizon. Safe to run repeatedly:
    an occurrence that already exists is skipped. Returns how many sessions were added."""
    now = now or datetime.now(UTC)
    series = (
        conn.execute(
            text("""
            SELECT ss.id, ss.tenant_id, ss.service_id, ss.location_id, ss.room_id,
                   ss.instructor_user_id, ss.capacity, ss.weekdays, ss.start_time,
                   ss.duration_minutes, ss.ends_on, t.time_zone
            FROM app.session_series ss JOIN app.tenants t ON t.id = ss.tenant_id
            WHERE ss.open_ended AND t.closed_at IS NULL
        """)
        )
        .mappings()
        .all()
    )

    added = 0
    for row in series:
        with tenant_scope(conn, row["tenant_id"]):
            local_today: date = now.astimezone(ZoneInfo(row["time_zone"])).date()
            target = local_today + timedelta(days=HORIZON_DAYS)
            if row["ends_on"] >= target:
                continue
            closed = set(
                conn.execute(
                    text("SELECT day FROM app.closed_days WHERE tenant_id = :t AND day > :after"),
                    {"t": row["tenant_id"], "after": row["ends_on"]},
                ).scalars()
            )
            starts = list(
                weekly_occurrences(
                    row["ends_on"] + timedelta(days=1),
                    target,
                    set(row["weekdays"]),
                    row["start_time"],
                    row["time_zone"],
                    skip=closed,
                )
            )
            if starts:
                added += conn.execute(
                    text("""
                        INSERT INTO app.sessions
                            (tenant_id, series_id, service_id, location_id, room_id,
                             instructor_user_id, capacity, starts_at, ends_at)
                        SELECT :tenant_id, :series_id, :service_id, :location_id, :room_id,
                               :instructor_user_id, :capacity, start_at,
                               start_at + make_interval(mins => :duration)
                        FROM unnest(CAST(:starts AS timestamptz[])) AS start_at
                        ON CONFLICT (series_id, starts_at) DO NOTHING
                    """),
                    {
                        "tenant_id": row["tenant_id"],
                        "series_id": row["id"],
                        "service_id": row["service_id"],
                        "location_id": row["location_id"],
                        "room_id": row["room_id"],
                        "instructor_user_id": row["instructor_user_id"],
                        "capacity": row["capacity"],
                        "duration": row["duration_minutes"],
                        "starts": starts,
                    },
                ).rowcount
            conn.execute(
                text("UPDATE app.session_series SET ends_on = :target WHERE id = :id"),
                {"target": target, "id": row["id"]},
            )
    return added


def remind_sessions(conn: Connection, now: datetime | None = None) -> int:
    """Notifies booked clients of today's classes (in each business's local date) that haven't
    started yet; once per booking. Run early each morning. Returns how many were reminded."""
    now = now or datetime.now(UTC)
    return conn.execute(
        text("""
            WITH due AS (
                UPDATE app.bookings b SET reminded_at = :now
                FROM app.sessions s, app.tenants t
                WHERE s.id = b.session_id AND t.id = b.tenant_id AND t.closed_at IS NULL
                  AND b.status = 'booked' AND b.reminded_at IS NULL
                  AND s.status = 'scheduled' AND s.starts_at > :now
                  AND (s.starts_at AT TIME ZONE t.time_zone)::date
                      = (CAST(:now AS timestamptz) AT TIME ZONE t.time_zone)::date
                RETURNING b.id, b.tenant_id, b.client_id, b.session_id
            )
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT d.tenant_id, d.client_id, 'session_reminder',
                   jsonb_build_object('session_id', s.id, 'service_name', sv.name,
                                      'starts_at', s.starts_at, 'booking_id', d.id)
            FROM due d
            JOIN app.sessions s ON s.id = d.session_id
            JOIN app.services sv ON sv.id = s.service_id
        """),
        {"now": now},
    ).rowcount


PLAN_ENDING_DAYS = 3


def remind_plans(conn: Connection, now: datetime | None = None) -> int:
    """Notifies clients whose last valid plan ends within PLAN_ENDING_DAYS (business-local
    dates) with nothing bought after it; once per plan. Returns how many were notified."""
    now = now or datetime.now(UTC)
    return conn.execute(
        text("""
            WITH local AS (
                SELECT id AS tenant_id,
                       (CAST(:now AS timestamptz) AT TIME ZONE time_zone)::date AS today
                FROM app.tenants WHERE closed_at IS NULL
            ),
            due AS (
                UPDATE app.entitlements e SET ending_notified_at = :now
                FROM local l, app.clients c
                WHERE l.tenant_id = e.tenant_id AND c.id = e.client_id
                  AND c.erased_at IS NULL
                  AND e.status = 'active' AND e.ending_notified_at IS NULL
                  AND e.ends_on BETWEEN l.today AND l.today + :days
                  AND NOT EXISTS (
                      SELECT 1 FROM app.entitlements later
                      WHERE later.client_id = e.client_id AND later.status = 'active'
                        AND later.id <> e.id AND later.ends_on > e.ends_on
                  )
                RETURNING e.id, e.tenant_id, e.client_id, e.name, e.ends_on
            )
            INSERT INTO app.notifications (tenant_id, client_id, kind, payload)
            SELECT tenant_id, client_id, 'plan_ending',
                   jsonb_build_object('plan_name', name, 'ends_on', ends_on,
                                      'entitlement_id', id)
            FROM due
        """),
        {"now": now, "days": PLAN_ENDING_DAYS},
    ).rowcount


AUTOMATED_KINDS = ("session_reminder", "plan_ending")
AUTOMATED_DETAILS = json.dumps({"channel": "whatsapp", "automated": True, "simulated": True})


def message_reminders(
    conn: Connection, now: datetime | None = None, messages_dir: Path = MESSAGES_DIR
) -> int:
    """Sends today's reminders over WhatsApp (simulated) for businesses with the messaging
    module and clients with a phone; once per notification. Run after the reminder jobs."""
    now = now or datetime.now(UTC)
    rows = (
        conn.execute(
            text("""
                SELECT n.id, n.tenant_id, n.client_id, n.kind, n.payload, c.first_name, c.phone,
                       t.name AS business, t.locale, t.time_zone
                FROM app.notifications n
                JOIN app.clients c ON c.id = n.client_id
                JOIN app.tenants t ON t.id = n.tenant_id
                WHERE n.kind = ANY(:kinds) AND n.created_at > :since AND t.closed_at IS NULL
                  AND c.erased_at IS NULL AND nullif(trim(c.phone), '') IS NOT NULL
                  AND EXISTS (SELECT 1 FROM app.tenant_modules m
                              WHERE m.tenant_id = n.tenant_id AND m.module_key = 'whatsapp')
                  AND NOT EXISTS (SELECT 1 FROM app.messages x WHERE x.notification_id = n.id)
                ORDER BY n.created_at
            """),
            {"kinds": list(AUTOMATED_KINDS), "since": now - timedelta(days=1)},
        )
        .mappings()
        .all()
    )
    texts: dict[str, dict] = {}
    per_tenant: dict[object, int] = {}
    simulated: dict[object, tuple[bool, str]] = {}
    for row in rows:
        with tenant_scope(conn, row["tenant_id"]):
            if row["tenant_id"] not in simulated:  # the business's messaging provider (X13)
                chosen = choose(conn, row["tenant_id"], "messaging")
                simulated[row["tenant_id"]] = (chosen.instance.simulated, chosen.info.name)
            is_simulated, provider = simulated[row["tenant_id"]]
            locale = row["locale"] if row["locale"] in ("he", "en") else "en"
            texts.setdefault(locale, load_messages(locale, messages_dir))
            _subject, body = render(texts[locale], row["kind"], row["payload"], row)
            conn.execute(
                text("""
                    INSERT INTO app.messages
                        (tenant_id, client_id, channel, to_phone, body, status, notification_id,
                         simulated, provider, sent_at)
                    VALUES (:t, :c, 'whatsapp', :phone, :body, :status, :n, :simulated, :provider,
                            CASE WHEN :simulated THEN now() END)
                """),
                {
                    "t": row["tenant_id"],
                    "c": row["client_id"],
                    "phone": row["phone"].strip(),
                    "body": body[:1100],
                    "n": row["id"],
                    "status": "sent" if is_simulated else "queued",
                    "simulated": is_simulated,
                    "provider": provider,
                },
            )
            per_tenant[row["tenant_id"]] = per_tenant.get(row["tenant_id"], 0) + 1
    for tenant_id, count in per_tenant.items():
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (:t, 'messages', :n, CAST(:details AS jsonb), 'reminders')
            """),
            {"t": tenant_id, "n": count, "details": AUTOMATED_DETAILS},
        )
    return sum(per_tenant.values())


FOLLOW_UP_AFTER_DAYS = 2  # a lead nobody has touched for this long gets one follow-up
FOLLOW_UP_WITHIN_DAYS = 30  # older leads are left to the team
FOLLOW_UP_DETAILS = json.dumps({"channel": "whatsapp", "automated": True, "lead_follow_up": True})


def follow_up_leads(
    conn: Connection, now: datetime | None = None, messages_dir: Path = MESSAGES_DIR
) -> int:
    """Leads on autopilot (#104, module crm_automation): a new or contacted lead with a phone
    that nobody has touched for two days gets one WhatsApp follow-up, written on its timeline.
    Needs the WhatsApp module too; never twice for the same lead."""
    now = now or datetime.now(UTC)
    rows = (
        conn.execute(
            text("""
                SELECT l.id, l.tenant_id, l.first_name, l.phone, l.interest,
                       t.name AS business, t.locale
                FROM app.leads l
                JOIN app.tenants t ON t.id = l.tenant_id
                WHERE l.stage IN ('new', 'contacted') AND t.closed_at IS NULL
                  AND nullif(trim(l.phone), '') IS NOT NULL
                  AND l.created_at > :now - make_interval(days => :within)
                  AND coalesce((SELECT max(a.occurred_at) FROM app.lead_activities a
                                WHERE a.lead_id = l.id), l.created_at)
                      < :now - make_interval(days => :after)
                  AND (SELECT count(*) FROM app.tenant_modules m WHERE m.tenant_id = l.tenant_id
                       AND m.module_key IN ('crm_automation', 'whatsapp')) = 2
                  AND NOT EXISTS (SELECT 1 FROM app.messages x
                                  WHERE x.lead_id = l.id AND x.created_by IS NULL)
                ORDER BY l.created_at
            """),
            {"now": now, "within": FOLLOW_UP_WITHIN_DAYS, "after": FOLLOW_UP_AFTER_DAYS},
        )
        .mappings()
        .all()
    )
    texts: dict[str, dict] = {}
    per_tenant: dict[object, int] = {}
    providers: dict[object, tuple[bool, str]] = {}
    for row in rows:
        with tenant_scope(conn, row["tenant_id"]):
            if row["tenant_id"] not in providers:  # the business's messaging provider (X13)
                chosen = choose(conn, row["tenant_id"], "messaging")
                providers[row["tenant_id"]] = (chosen.instance.simulated, chosen.info.name)
            simulated, provider = providers[row["tenant_id"]]
            locale = row["locale"] if row["locale"] in ("he", "en") else "en"
            texts.setdefault(locale, load_messages(locale, messages_dir))
            interest = (row["interest"] or "").strip()
            template = texts[locale]["leadFollowUp"]["withInterest" if interest else "plain"]
            body = (
                template.replace("{name}", row["first_name"])
                .replace("{business}", row["business"])
                .replace("{interest}", interest[:200])
            )[:1100]
            conn.execute(
                text("""
                    INSERT INTO app.messages
                        (tenant_id, lead_id, channel, to_phone, body, status, simulated, provider,
                         sent_at)
                    VALUES (:t, :l, 'whatsapp', :phone, :body, :status, :simulated, :provider,
                            CASE WHEN :simulated THEN now() END)
                """),
                {
                    "t": row["tenant_id"],
                    "l": row["id"],
                    "phone": row["phone"].strip(),
                    "body": body,
                    "status": "sent" if simulated else "queued",
                    "simulated": simulated,
                    "provider": provider,
                },
            )
            conn.execute(
                text("""
                    INSERT INTO app.lead_activities (tenant_id, lead_id, kind, note)
                    VALUES (:t, :l, 'message', :note)
                """),
                {"t": row["tenant_id"], "l": row["id"], "note": body[:2000]},
            )
            per_tenant[row["tenant_id"]] = per_tenant.get(row["tenant_id"], 0) + 1
    for tenant_id, count in per_tenant.items():
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (:t, 'messages', :n, CAST(:details AS jsonb), 'lead-follow-ups')
            """),
            {"t": tenant_id, "n": count, "details": FOLLOW_UP_DETAILS},
        )
    return sum(per_tenant.values())


# How long data is kept (decision X20). A business that closed its account is deleted after
# CLOSED_BUSINESS_GRACE_DAYS (delete_closed_businesses below).
RETENTION_MONTHS = {
    "leads": 12,
    "contact_requests": 12,
    "ai_conversations": 12,
    "whatsapp_conversations": 12,  # AI chats, on WhatsApp
    "whatsapp_inbox": 12,  # the clients' messages those chats answered
    "messages": 24,
    "audit_log": 24,  # the owner's record of who did what
}


PURGE_BATCH = 5000  # rows per DELETE


def purge_expired(conn: Connection, now: datetime | None = None) -> dict[str, int]:
    """Deletes what has passed its time: leads that never became clients and nobody touched,
    website and in-app requests, the AI's conversations (in the app and on WhatsApp) with the
    WhatsApp messages they answered, the message log, the audit log and files past their expiry."""
    now = now or datetime.now(UTC)

    def before(kind: str) -> datetime:
        return now - timedelta(days=round(RETENTION_MONTHS[kind] * 30.44))

    # Each statement deletes at most PURGE_BATCH rows; _delete_in_batches repeats it.
    statements = {
        "leads": """
            DELETE FROM app.leads WHERE ctid = ANY(ARRAY(
                SELECT l.ctid FROM app.leads l
                WHERE l.client_id IS NULL
                  AND greatest(l.updated_at, coalesce((SELECT max(a.occurred_at)
                      FROM app.lead_activities a WHERE a.lead_id = l.id), l.updated_at)) < :before
                LIMIT :batch))
        """,
        "contact_requests": """
            DELETE FROM app.contact_requests WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.contact_requests
                WHERE created_at < :before LIMIT :batch))
        """,
        "ai_conversations": """
            DELETE FROM app.ai_conversations WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.ai_conversations
                WHERE updated_at < :before LIMIT :batch))
        """,
        "whatsapp_conversations": """
            DELETE FROM app.whatsapp_conversations WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.whatsapp_conversations
                WHERE updated_at < :before LIMIT :batch))
        """,
        "whatsapp_inbox": """
            DELETE FROM app.whatsapp_inbox WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.whatsapp_inbox
                WHERE received_at < :before LIMIT :batch))
        """,
        "messages": """
            DELETE FROM app.messages WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.messages
                WHERE created_at < :before LIMIT :batch))
        """,
        "audit_log": """
            DELETE FROM app.audit_log WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.audit_log
                WHERE occurred_at < :before LIMIT :batch))
        """,
    }
    deleted = {
        kind: _delete_in_batches(conn, sql, before(kind)) for kind, sql in statements.items()
    }
    deleted["data_exports"] = purge_expired_exports(conn)
    deleted["files"] = purge_expired_files(conn)  # e.g. the imports folder keeps files 30 days
    return deleted


def _delete_in_batches(conn: Connection, sql: str, before: datetime) -> int:
    """Runs a statement that deletes up to :batch rows until it deletes fewer, so no single
    statement holds millions of rows (and their locks) at once."""
    total = 0
    while True:
        count = conn.execute(text(sql), {"before": before, "batch": PURGE_BATCH}).rowcount
        total += count
        if count < PURGE_BATCH:
            return total


def purge_expired_exports(conn: Connection) -> int:
    """Deletes business exports past their 24 hours, from storage too."""
    rows = conn.execute(
        text("DELETE FROM app.data_exports WHERE expires_at < now() RETURNING storage_key")
    ).all()
    _forget_keys(conn, [key for (key,) in rows if key])
    return len(rows)


def _forget_keys(conn: Connection, keys: list[str]) -> None:
    storage = None
    for key in keys:
        storage = storage or choose(conn, None, "storage").instance
        forget(storage, key)


def delete_closed_businesses(
    conn: Connection, now: datetime | None = None, apply: bool = False
) -> dict[str, int | list[str]]:
    """Deletes businesses whose owner closed the account more than CLOSED_BUSINESS_GRACE_DAYS ago,
    with everything under them (every tenant table cascades). Irreversible, so it only reports
    what it would delete unless `apply` is true. People's sign-in accounts are kept: they may
    own or work in other businesses. Each deletion is noted in the MyBiz audit log."""
    now = now or datetime.now(UTC)
    due = (
        conn.execute(
            text("""
                SELECT id, name, closed_at FROM app.tenants
                WHERE closed_at < :before ORDER BY closed_at
            """),
            {"before": now - timedelta(days=CLOSED_BUSINESS_GRACE_DAYS)},
        )
        .mappings()
        .all()
    )
    if apply:
        for business in due:
            with tenant_scope(conn, business["id"]):
                conn.execute(
                    text("""
                        INSERT INTO app.platform_audit (actor_email, action, details)
                        VALUES ('system', 'business.deleted', jsonb_build_object(
                            'business_id', CAST(:id AS text), 'name', CAST(:name AS text),
                            'closed_at', CAST(:closed_at AS text)))
                    """),
                    {
                        "id": business["id"],
                        "name": business["name"],
                        "closed_at": business["closed_at"],
                    },
                )
                # The files in the storage provider are not under the tenant row, so they go first.
                keys = conn.execute(
                    text("""
                        SELECT storage_key FROM app.client_documents
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                        UNION ALL SELECT storage_key FROM app.business_files
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                        UNION ALL SELECT storage_key FROM app.data_exports
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                    """),
                    {"id": business["id"]},
                ).scalars()
                _forget_keys(conn, list(keys))
                conn.execute(text("DELETE FROM app.tenants WHERE id = :id"), {"id": business["id"]})
    return {
        "dry_run": 0 if apply else 1,
        "businesses": len(due),
        "ids": [str(business["id"]) for business in due],
    }


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


JOBS = {
    "extend-series": extend_series,
    "remind-sessions": remind_sessions,
    "remind-plans": remind_plans,
    "send-emails": send_notification_emails,
    "notify-shifts": notify_shifts,
    "remind-payroll": remind_payroll_job,
    "notify-payslips": notify_payslips,
    "message-reminders": message_reminders,
    "follow-up-leads": follow_up_leads,
    "purge-expired": purge_expired,
    "delete-closed-businesses": delete_closed_businesses,
    "bill-businesses": bill_businesses,
    "dunning": run_dunning,
    "publish-shifts": publish_shifts,
    "send-messages": send_messages,
    "send-announcements": send_announcements,
    "answer-whatsapp": answer_inbox,
    "issue-documents": issue_documents,
    "move-files": move_files,
    "run-ai-tasks": run_ai_tasks,
    "sync-social": sync_social,
    "rotate-secrets": rotate_secrets,
}

# Jobs that only report unless told `--apply`.
APPLY_JOBS = (delete_closed_businesses, rotate_secrets)

# How often each scheduled job must succeed, in hours: the schedule plus slack for a delayed
# run (GitHub's scheduler can start a run late). check-jobs reports a job as late after that.
DAILY = [
    "extend-series",
    "remind-sessions",
    "remind-plans",
    "remind-payroll",
    "bill-businesses",
    "dunning",
    "message-reminders",
    "follow-up-leads",
    "purge-expired",
    "delete-closed-businesses",
    "send-messages",
    "issue-documents",
    "sync-social",
]
HOURLY = [
    "publish-shifts",
    "send-emails",
    "notify-shifts",
    "send-announcements",
    "notify-payslips",
]
# GitHub's free scheduler throttles "hourly" crons on staging to a run every 1-6 hours (observed
# gaps up to ~6h), so an hourly job is late only after 8 hours without a success.
MAX_HOURS = {**{job: 27 for job in DAILY}, **{job: 8 for job in HOURLY}}
# Jobs whose staging workflow runs only once an email provider is set: they count as late only
# after they have run at least once.
OPTIONAL = {"send-emails", "notify-shifts"}


JOBS_ROLE = "app_jobs"


def jobs_engine(database_url: str, role: str | None = JOBS_ROLE) -> Engine:
    """An engine whose every connection runs as the least-privilege jobs role."""
    engine = create_engine(database_url)
    if role:

        @event.listens_for(engine, "connect")
        def _use_jobs_role(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f'SET ROLE "{role}"')
            cursor.close()
            dbapi_connection.commit()

    return engine


def run_job(engine: Engine, name: str, apply: bool = False) -> object:
    """Runs one job in its own transaction and records the run in app.job_runs, failed runs
    included (the record is written apart from the job, so a rollback doesn't lose it).

    A job never runs twice at once: it holds an advisory lock for its whole run, and a second
    start (a delayed cron overlapping the next one) records itself as skipped and returns. The
    run also records how many businesses were handled and how many failed (see tenant_scope)."""
    with engine.connect() as lock:
        got = lock.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
            {"key": f"{LOCK_PREFIX}{name}"},
        ).scalar_one()
        lock.commit()  # the lock belongs to the session, not to this transaction
        if not got:
            return _record_skip(engine, name)
        try:
            return _run_locked(engine, name, apply)
        finally:
            lock.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                {"key": f"{LOCK_PREFIX}{name}"},
            )
            lock.commit()


def _record_skip(engine: Engine, name: str) -> str:
    result = "skipped: the previous run of this job is still going"
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app.job_runs (job, finished_at, ok, result)
                VALUES (:job, now(), false, :result)
            """),
            {"job": name, "result": result},
        )
    return result


def _run_locked(engine: Engine, name: str, apply: bool) -> object:
    with engine.begin() as conn:
        run_id = conn.execute(
            text("INSERT INTO app.job_runs (job) VALUES (:job) RETURNING id"), {"job": name}
        ).scalar_one()
    ok, result, tally = False, None, Tally()
    try:
        with engine.begin() as conn:
            tally = start_tally(conn)
            job = JOBS[name]
            result = job(conn, apply=apply) if job in APPLY_JOBS else job(conn)
        ok = True
        return result
    except Exception as error:
        result = f"{type(error).__name__}: {error}"
        _alert_failure(engine, name, run_id, result)
        raise
    finally:
        recorded = str(result)
        if tally.failed:
            recorded = f"{recorded} | {tally.summary()}"
            print(f"{name}: {tally.summary()}", file=sys.stderr)
        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE app.job_runs
                SET finished_at = now(), ok = :ok, result = :result,
                    succeeded = :succeeded, failed = :failed
                WHERE id = :id
            """),
                {
                    "id": run_id,
                    "ok": ok,
                    "result": recorded[:2000],
                    "succeeded": tally.succeeded,
                    "failed": len(tally.failed),
                },
            )


def notify_team(engine: Engine, title: str, body: str) -> AlertResult:
    """Alerts the MyBiz owners (push, then email). Never raises: a broken alert channel must not
    hide the failure that is being reported, which is also in the logs and the job runs."""
    try:
        sender = sender_from_settings()
    except SystemExit:  # a provider without its key
        sender = None
    try:
        with engine.begin() as conn:
            return alert_team(conn, title, body, push_sender_from_settings(), sender)
    except Exception as error:
        print(f"alert not sent: {type(error).__name__}: {error}", file=sys.stderr)
        return AlertResult()


def _alert_failure(engine: Engine, name: str, run_id: int, error: str) -> None:
    """Alerts when a job starts failing, once: a job that was already failing on its previous
    run does not alert again (the daily check-jobs reminds while it stays broken)."""
    try:
        with engine.connect() as conn:
            previous_ok = conn.execute(
                text("""
                    SELECT ok FROM app.job_runs
                    WHERE job = :job AND id < :id AND finished_at IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                """),
                {"job": name, "id": run_id},
            ).scalar()
    except Exception:
        previous_ok = None
    if previous_ok is False:
        return
    notify_team(
        engine,
        f"{NAME} job failed: {name}",
        f"{name} failed on {get_settings().environment}.\n\n{error[:300]}",
    )


def late_jobs(conn: Connection, now: datetime | None = None) -> list[dict]:
    """The scheduled jobs whose last successful run is older than they allow (or never ran)."""
    now = now or datetime.now(UTC)
    last = dict(
        conn.execute(
            text("SELECT job, max(finished_at) FROM app.job_runs WHERE ok GROUP BY job")
        ).all()
    )
    return [
        {"job": job, "last_ok": last.get(job), "max_hours": hours}
        for job, hours in MAX_HOURS.items()
        if (last.get(job) is None and job not in OPTIONAL)
        or (last.get(job) is not None and now - last[job] > timedelta(hours=hours))
    ]


def run_group(engine: Engine, names: list[str]) -> list[str]:
    """Runs jobs one after another; a failure is recorded and the rest still run.
    Returns the names of the jobs that failed."""
    failed = []
    for name in names:
        try:
            print(f"{name}: {run_job(engine, name)}")
        except Exception as error:
            print(f"{name}: FAILED {type(error).__name__}: {error}", file=sys.stderr)
            failed.append(name)
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a background job.")
    parser.add_argument(
        "job", choices=[*JOBS, "run-daily", "run-hourly", "check-jobs", "test-alert"]
    )
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Really change data (delete-closed-businesses, rotate-secrets: a report without it)",
    )
    args = parser.parse_args()
    settings = get_settings()
    engine = jobs_engine(args.database_url or settings.database_url, settings.jobs_db_role)
    if args.job == "check-jobs":
        with engine.connect() as conn:
            late = late_jobs(conn)
        for item in late:
            last = item["last_ok"].isoformat() if item["last_ok"] else "never"
            # The ::error:: prefix shows as an annotation on the GitHub run.
            print(
                f"::error::{item['job']} is late: last success {last}, "
                f"expected every {item['max_hours']}h at most"
            )
        print(f"check-jobs: {len(late)} late of {len(MAX_HOURS)}")
        if late:
            names = ", ".join(item["job"] for item in late)
            sent = notify_team(
                engine,
                f"{NAME}: {len(late)} background job(s) late",
                f"Late on {get_settings().environment}: {names}.",
            )
            print(f"alert: {sent.pushed} push, {sent.emailed} email, {sent.recipients} owners")
        sys.exit(1 if late else 0)
    if args.job == "test-alert":
        sent = notify_team(
            engine,
            f"{NAME} test alert",
            f"If this reached your phone, alerts work ({get_settings().environment}).",
        )
        print(f"test-alert: {sent.pushed} push, {sent.emailed} email, {sent.recipients} owners")
        sys.exit(0 if sent.pushed or sent.emailed else 1)
    if args.job in ("run-daily", "run-hourly"):
        failed = run_group(engine, DAILY if args.job == "run-daily" else HOURLY)
        sys.exit(1 if failed else 0)
    print(f"{args.job}: {run_job(engine, args.job, apply=args.apply)}")


if __name__ == "__main__":
    main()
