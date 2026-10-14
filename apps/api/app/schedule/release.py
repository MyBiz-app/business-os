"""When clients may book classes: a rolling horizon, or a weekly release of the next week."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schedule.scheduling import local_to_utc

MAX_AHEAD_DAYS = 28  # the team cannot publish further ahead than this


@dataclass(frozen=True)
class Release:
    published_until: date  # the last local date clients can book (inclusive)
    next_release_at: datetime | None  # when more opens by itself (weekly release only)

    def opens_before(self, time_zone: str) -> datetime:
        """The first instant that is not bookable yet."""
        return local_to_utc(self.published_until + timedelta(days=1), time.min, time_zone)


def compute_release(
    now: datetime,
    time_zone: str,
    horizon_days: int,
    weekday: int | None,
    at: time | None,
    published_until: date | None,
) -> Release:
    """Weeks run Sunday to Saturday. With a weekly release, the rest of this week is open, and on
    the release moment the whole next week opens too. Without one, `horizon_days` days from today
    (today included) are open. Publishing early can only open more."""
    zone = ZoneInfo(time_zone)
    local_now = now.astimezone(zone)
    today = local_now.date()
    next_release: datetime | None = None
    if weekday is None or at is None:
        until = today + timedelta(days=horizon_days - 1)
    else:
        week_start = today - timedelta(days=(today.weekday() + 1) % 7)
        release = datetime.combine(week_start + timedelta(days=(weekday + 1) % 7), at, tzinfo=zone)
        if local_now >= release:
            until = week_start + timedelta(days=13)
            release += timedelta(days=7)
        else:
            until = week_start + timedelta(days=6)
        next_release = release.astimezone(UTC)
    if published_until is not None and published_until > until:
        until = published_until
    return Release(until, next_release)


def load_release(db: Session, now: datetime | None = None) -> tuple[Release, str]:
    """The current business's release (the signed-in team member's or client's) and time zone."""
    row = (
        db.execute(
            text("""
                SELECT time_zone, booking_horizon_days, weekly_release_weekday,
                       weekly_release_time, schedule_published_until
                FROM app.tenants
                WHERE id = coalesce(app.current_tenant_id(), app.client_tenant_id())
            """)
        )
        .mappings()
        .one()
    )
    release = compute_release(
        now or datetime.now(UTC),
        row["time_zone"],
        row["booking_horizon_days"],
        row["weekly_release_weekday"],
        row["weekly_release_time"],
        row["schedule_published_until"],
    )
    return release, row["time_zone"]
