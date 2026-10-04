"""Free appointment times: a staff member's working hours on a day, minus their busy time.

Pure computation (no database), so it is easy to test; app/api/appointments.py loads the hours
and busy intervals. Times are local to the business; the result is UTC instants."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.scheduling import local_to_utc

STEP_MINUTES = 15  # offered start times are on a quarter-hour grid


@dataclass(frozen=True)
class Hours:
    starts: time
    ends: time


def free_starts(
    day: date,
    hours: Iterable[Hours],
    busy: Iterable[tuple[datetime, datetime]],
    duration_minutes: int,
    time_zone: str,
    *,
    now: datetime | None = None,
    step_minutes: int = STEP_MINUTES,
) -> list[datetime]:
    """Start instants on `day` where an appointment of `duration_minutes` fits inside working
    hours without overlapping a busy interval, and that are still in the future."""
    now = now or datetime.now(UTC)
    length = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=step_minutes)
    busy_list = sorted(busy)
    found: set[datetime] = set()
    for block in hours:
        start = local_to_utc(day, block.starts, time_zone)
        end = local_to_utc(day, block.ends, time_zone)
        candidate = start
        while candidate + length <= end:
            finish = candidate + length
            if candidate > now and not any(
                b_start < finish and b_end > candidate for b_start, b_end in busy_list
            ):
                found.add(candidate)
            candidate += step
    return sorted(found)
