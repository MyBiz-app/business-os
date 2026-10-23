"""Booking series: the dates of a standing booking (slice C5).

"Every Tuesday 19:00" means 19:00 on the business's clock, also across a clock change, so the
dates are worked out in the business's time zone and only then turned into UTC instants."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schedule.scheduling import local_to_utc


def occurrence_starts(
    first: datetime, every_weeks: int, occurrences: int, time_zone: str
) -> Iterator[datetime]:
    local = first.astimezone(ZoneInfo(time_zone))
    for n in range(occurrences):
        day = local.date() + timedelta(weeks=every_weeks * n)
        yield local_to_utc(day, local.time(), time_zone)
