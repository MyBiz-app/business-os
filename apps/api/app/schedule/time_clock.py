"""Hours worked and overtime from time clock entries (round 6, P2).

Pure functions: the rules come in as data (`ClockRules`, stored per business in
`time_clock_rules`), nothing is hard-coded to one country's numbers. The default rules are the
Israeli ones: a 42 hour week, a day of 8.6 hours (5 work days) or 8 (6 work days), the first
2 overtime hours of a day at 125%, the rest at 150%, and work on the weekly rest day at 150%.

An entry that crosses midnight is split at midnight in the business's time zone, so each hour
lands on the day it was worked. Overtime is counted per day first; on top of that, regular hours
past the week's limit become overtime too (they take the same 125% / 150% steps, per day)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ClockRules:
    work_days_per_week: int = 5
    week_hours: float = 42
    day_hours_5: float = 8.6
    day_hours_6: float = 8
    tier1_hours: float = 2
    tier1_percent: int = 125
    tier2_percent: int = 150
    rest_day_percent: int = 150
    rest_weekday: int = 5  # Monday is 0, so 5 is Saturday

    @property
    def day_hours(self) -> float:
        return self.day_hours_6 if self.work_days_per_week == 6 else self.day_hours_5


@dataclass
class Breakdown:
    """Hours worked in a period, by pay rate. `weighted` is regular hours plus each overtime
    hour times its rate (what the person is paid for, in "100% hours")."""

    regular: float = 0
    tier1: float = 0  # overtime at `tier1_percent`
    tier2: float = 0  # overtime at `tier2_percent`
    rest_day: float = 0  # work on the weekly rest day, at `rest_day_percent`
    total: float = 0
    weighted: float = 0
    days: dict[date, float] = field(default_factory=dict)


def split_by_day(start: datetime, end: datetime, time_zone: str) -> dict[date, float]:
    """The hours of one stretch of work, per local calendar day."""
    zone = ZoneInfo(time_zone)
    cursor, result = start.astimezone(zone), end.astimezone(zone)
    hours: dict[date, float] = {}
    while cursor < result:
        midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=zone)
        stop = min(result, midnight)
        hours[cursor.date()] = hours.get(cursor.date(), 0) + (stop - cursor).total_seconds() / 3600
        cursor = stop
    return hours


def _week_start(day: date) -> date:
    """Weeks run Sunday to Saturday."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def compute(day_hours: dict[date, float], rules: ClockRules) -> Breakdown:
    """Pay-rate breakdown of the hours worked per day."""
    result = Breakdown()
    week_regular: dict[date, float] = defaultdict(float)
    for day in sorted(day_hours):
        worked = day_hours[day]
        result.days[day] = round(worked, 4)
        result.total += worked
        if day.weekday() == rules.rest_weekday:
            result.rest_day += worked
            continue
        regular = min(worked, rules.day_hours)
        overtime = worked - regular
        # Regular hours past the week's limit are overtime as well.
        room = max(0.0, rules.week_hours - week_regular[_week_start(day)])
        if regular > room:
            overtime += regular - room
            regular = room
        week_regular[_week_start(day)] += regular
        result.regular += regular
        first = min(overtime, rules.tier1_hours)
        result.tier1 += first
        result.tier2 += overtime - first
    result.weighted = (
        result.regular
        + result.tier1 * rules.tier1_percent / 100
        + result.tier2 * rules.tier2_percent / 100
        + result.rest_day * rules.rest_day_percent / 100
    )
    for name in ("regular", "tier1", "tier2", "rest_day", "total", "weighted"):
        setattr(result, name, round(getattr(result, name), 2))
    return result
