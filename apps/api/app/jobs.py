"""Background jobs, run on a schedule (see .github/workflows/jobs-staging.yml).

    uv run python -m app.jobs extend-series [--database-url URL]
    uv run python -m app.jobs remind-sessions
    uv run python -m app.jobs remind-plans
    uv run python -m app.jobs send-emails     (needs API_EMAIL_PROVIDER; see app/email.py)
    uv run python -m app.jobs bill-businesses (simulated platform billing; see app/billing.py)

Jobs run with the migration (owner) connection, across all businesses, so they must only do
system work that needs no user's permission."""

import argparse
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, create_engine, text

from app.billing import bill_businesses
from app.core.config import get_settings
from app.email import send_emails, sender_from_settings
from app.scheduling import weekly_occurrences

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
            WHERE ss.open_ended
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
                WHERE s.id = b.session_id AND t.id = b.tenant_id
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
                FROM app.tenants
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


def send_notification_emails(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    if sender is None:
        return "email provider not configured; nothing sent"
    return send_emails(conn, sender)


JOBS = {
    "extend-series": extend_series,
    "remind-sessions": remind_sessions,
    "remind-plans": remind_plans,
    "send-emails": send_notification_emails,
    "bill-businesses": bill_businesses,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a background job.")
    parser.add_argument("job", choices=list(JOBS))
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    args = parser.parse_args()
    engine = create_engine(args.database_url or get_settings().database_url)
    with engine.begin() as conn:
        result = JOBS[args.job](conn)
    print(f"{args.job}: {result}")


if __name__ == "__main__":
    main()
