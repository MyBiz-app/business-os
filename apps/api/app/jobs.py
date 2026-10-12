"""Background jobs, run on a schedule (see .github/workflows/jobs-staging.yml).

    uv run python -m app.jobs extend-series [--database-url URL]
    uv run python -m app.jobs remind-sessions
    uv run python -m app.jobs remind-plans
    uv run python -m app.jobs send-emails     (needs API_EMAIL_PROVIDER; see app/messaging/email.py)
    uv run python -m app.jobs message-reminders (WhatsApp copies of today's reminders, simulated)
    uv run python -m app.jobs bill-businesses (simulated platform billing; app/commerce/billing.py)
    uv run python -m app.jobs notify-shifts    (emails staff new and edited published shifts)
    uv run python -m app.jobs publish-shifts  (hourly: the shifts roster goes out on schedule)
    uv run python -m app.jobs send-messages   (the outbox, through each business's provider)
    uv run python -m app.jobs issue-documents (receipts to each business's invoicing provider)
    uv run python -m app.jobs delete-closed-businesses [--apply] (dry run unless --apply)
    uv run python -m app.jobs move-files      (documents kept in the database → the object store)
    uv run python -m app.jobs run-daily       (every daily job in turn, for a cron service)
    uv run python -m app.jobs run-hourly      (every hourly job in turn)
    uv run python -m app.jobs check-jobs      (fails when a scheduled job is late)

Every run is recorded in app.job_runs (started, finished, ok, result), so a job that stopped
running or keeps failing is noticed by check-jobs (.github/workflows/check-jobs-staging.yml).

Jobs run with the migration (owner) connection, across all businesses, so they must only do
system work that needs no user's permission."""

import argparse
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, Engine, create_engine, text

from app.commerce.billing import bill_businesses
from app.core.config import get_settings
from app.core.retention import CLOSED_BUSINESS_GRACE_DAYS
from app.messaging import outbox
from app.messaging.email import (
    MESSAGES_DIR,
    load_messages,
    render,
    send_emails,
    sender_from_settings,
)
from app.messaging.roster import notify_roster, notify_roster_changes
from app.providers.choice import choose
from app.providers.storage import tenant_key
from app.schedule.scheduling import weekly_occurrences

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
    return len(rows)


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
    return len(rows)


# How long data is kept (decision X20). A business that closed its account is deleted after
# CLOSED_BUSINESS_GRACE_DAYS (delete_closed_businesses below).
RETENTION_MONTHS = {"leads": 12, "contact_requests": 12, "ai_conversations": 12, "messages": 24}


def purge_expired(conn: Connection, now: datetime | None = None) -> dict[str, int]:
    """Deletes what has passed its time: leads that never became clients and nobody touched,
    website and in-app requests, the AI assistant's conversations, and the message log."""
    now = now or datetime.now(UTC)

    def before(kind: str) -> datetime:
        return now - timedelta(days=round(RETENTION_MONTHS[kind] * 30.44))

    statements = {
        "leads": """
            DELETE FROM app.leads l
            WHERE l.client_id IS NULL
              AND greatest(l.updated_at, coalesce((SELECT max(a.occurred_at)
                  FROM app.lead_activities a WHERE a.lead_id = l.id), l.updated_at)) < :before
        """,
        "contact_requests": "DELETE FROM app.contact_requests WHERE created_at < :before",
        "ai_conversations": "DELETE FROM app.ai_conversations WHERE updated_at < :before",
        "messages": "DELETE FROM app.messages WHERE created_at < :before",
    }
    return {
        kind: conn.execute(text(sql), {"before": before(kind)}).rowcount
        for kind, sql in statements.items()
    }


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


def issue_documents(conn: Connection) -> dict[str, int]:
    return outbox.issue_documents(conn)


def notify_shifts(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    if sender is None:
        return "email provider not configured; nothing sent"
    published = notify_roster(conn, sender)
    edits = notify_roster_changes(conn, sender)
    return published | {f"changes_{key}": value for key, value in edits.items()}


def send_notification_emails(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    if sender is None:
        return "email provider not configured; nothing sent"
    return send_emails(conn, sender)


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


JOBS = {
    "extend-series": extend_series,
    "remind-sessions": remind_sessions,
    "remind-plans": remind_plans,
    "send-emails": send_notification_emails,
    "notify-shifts": notify_shifts,
    "message-reminders": message_reminders,
    "follow-up-leads": follow_up_leads,
    "purge-expired": purge_expired,
    "delete-closed-businesses": delete_closed_businesses,
    "bill-businesses": bill_businesses,
    "publish-shifts": publish_shifts,
    "send-messages": send_messages,
    "issue-documents": issue_documents,
    "move-files": move_files,
}

# How often each scheduled job must succeed, in hours: the schedule plus slack for a delayed
# run (GitHub's scheduler can start a run late). check-jobs reports a job as late after that.
DAILY = [
    "extend-series",
    "remind-sessions",
    "remind-plans",
    "bill-businesses",
    "message-reminders",
    "follow-up-leads",
    "purge-expired",
    "delete-closed-businesses",
    "send-messages",
    "issue-documents",
]
HOURLY = ["publish-shifts", "send-emails", "notify-shifts"]
MAX_HOURS = {**{job: 27 for job in DAILY}, **{job: 3 for job in HOURLY}}
# Jobs whose staging workflow runs only once an email provider is set: they count as late only
# after they have run at least once.
OPTIONAL = {"send-emails", "notify-shifts"}


def run_job(engine: Engine, name: str, apply: bool = False) -> object:
    """Runs one job in its own transaction and records the run in app.job_runs, failed runs
    included (the record is written apart from the job, so a rollback doesn't lose it)."""
    with engine.begin() as conn:
        run_id = conn.execute(
            text("INSERT INTO app.job_runs (job) VALUES (:job) RETURNING id"), {"job": name}
        ).scalar_one()
    ok, result = False, None
    try:
        with engine.begin() as conn:
            job = JOBS[name]
            result = job(conn, apply=apply) if job is delete_closed_businesses else job(conn)
        ok = True
        return result
    except Exception as error:
        result = f"{type(error).__name__}: {error}"
        raise
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE app.job_runs SET finished_at = now(), ok = :ok, result = :result
                WHERE id = :id
            """),
                {"id": run_id, "ok": ok, "result": str(result)[:2000]},
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
    parser.add_argument("job", choices=[*JOBS, "run-daily", "run-hourly", "check-jobs"])
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Really delete (delete-closed-businesses only reports without it)",
    )
    args = parser.parse_args()
    engine = create_engine(args.database_url or get_settings().database_url)
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
        sys.exit(1 if late else 0)
    if args.job in ("run-daily", "run-hourly"):
        failed = run_group(engine, DAILY if args.job == "run-daily" else HOURLY)
        sys.exit(1 if failed else 0)
    print(f"{args.job}: {run_job(engine, args.job, apply=args.apply)}")


if __name__ == "__main__":
    main()
