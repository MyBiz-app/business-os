"""Background jobs, run on a schedule (see .github/workflows/jobs-staging.yml).

    uv run python -m app.jobs extend-series [--database-url URL]
    uv run python -m app.jobs send-emails     (needs API_EMAIL_PROVIDER; see app/email.py)

Jobs run with the migration (owner) connection, across all businesses, so they must only do
system work that needs no user's permission."""

import argparse
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, create_engine, text

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
        starts = list(
            weekly_occurrences(
                row["ends_on"] + timedelta(days=1),
                target,
                set(row["weekdays"]),
                row["start_time"],
                row["time_zone"],
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


def send_notification_emails(conn: Connection) -> dict[str, int] | str:
    sender = sender_from_settings()
    if sender is None:
        return "email provider not configured; nothing sent"
    return send_emails(conn, sender)


JOBS = {"extend-series": extend_series, "send-emails": send_notification_emails}


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
