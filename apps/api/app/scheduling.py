"""Recurrence expansion: pure functions, no database."""

from collections.abc import Collection, Iterator
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def local_to_utc(day: date, at: time, time_zone: str) -> datetime:
    """A wall-clock time in the business's time zone, as an aware UTC datetime."""
    return datetime.combine(day, at, tzinfo=ZoneInfo(time_zone)).astimezone(UTC)


def weekly_occurrences(
    starts_on: date,
    ends_on: date,
    weekdays: set[int],
    start_time: time,
    time_zone: str,
    skip: Collection[date] = (),
) -> Iterator[datetime]:
    """Start instants (UTC) of a weekly series. Weekdays are 0 = Monday … 6 = Sunday; days in
    `skip` (the business's closed days) are left out.

    Each occurrence is computed from its own local date, so 18:00 stays 18:00 local
    across daylight-saving changes (its UTC offset changes instead)."""
    day = starts_on
    while day <= ends_on:
        if day.weekday() in weekdays and day not in skip:
            yield local_to_utc(day, start_time, time_zone)
        day += timedelta(days=1)
