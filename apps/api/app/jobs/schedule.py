"""Jobs about the schedule: extending series and reminding clients."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.core.tenant_scope import tenant_scope
from app.jobs.base import HORIZON_DAYS
from app.messaging.email import (
    MESSAGES_DIR,
    load_messages,
    render,
)
from app.providers.choice import choose
from app.schedule.scheduling import weekly_occurrences


def extend_series(conn: Connection, now: datetime | None = None) -> int:
    """Adds occurrences to open-ended series up to the horizon. Safe to run repeatedly:
    an occurrence that already exists is skipped. Returns how many sessions were added."""
    now = now or datetime.now(UTC)
    series = (
        conn.execute(
            text("""
            SELECT ss.id, ss.tenant_id, ss.service_id, ss.location_id, ss.room_id,
                   ss.instructor_user_id, ss.extra_instructor_user_ids, ss.capacity, ss.weekdays,
                   ss.start_time,
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
                if row["extra_instructor_user_ids"]:
                    # The new sessions get the series's team (members who left are skipped).
                    conn.execute(
                        text("""
                            INSERT INTO app.session_instructors (tenant_id, session_id, user_id)
                            SELECT s.tenant_id, s.id, m.user_id
                            FROM app.sessions s
                            JOIN app.tenant_members m ON m.tenant_id = s.tenant_id
                                AND m.user_id = ANY(CAST(:team AS uuid[]))
                            WHERE s.series_id = :series_id
                              AND s.starts_at = ANY(CAST(:starts AS timestamptz[]))
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            "team": [str(i) for i in row["extra_instructor_user_ids"]],
                            "series_id": row["id"],
                            "starts": starts,
                        },
                    )
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
